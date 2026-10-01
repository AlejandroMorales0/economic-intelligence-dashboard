import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from economic_dashboard.cli import main
from economic_dashboard.fred import FredClient, IngestionError, validate_range
from economic_dashboard.ingestion import ingest_unrate, normalize
from economic_dashboard.lambda_handler import handler


def row(period="2024-01-01", value="3.7"):
    return {"date": period, "value": value,
            "realtime_start": "2024-03-01", "realtime_end": "2024-03-01"}


def page(rows, count=None, offset=0):
    return {"observations": rows, "count": len(rows) if count is None else count,
            "offset": offset}


def response(payload):
    return io.StringIO(json.dumps(payload))


class FredTests(unittest.TestCase):
    def test_credentials_and_ranges(self):
        with self.assertRaises(IngestionError):
            FredClient(" ")
        for start, end in [("2024-1-01", None), ("2024-02-30", None),
                           ("2024-03-01", "2024-01-01")]:
            with self.assertRaises(IngestionError):
                validate_range(start, end)

    def test_pagination_and_request_parameters(self):
        opener = Mock(side_effect=[response(page([row()], 2)),
                                   response(page([row("2024-02-01")], 2, 1))])
        pages = FredClient("test-secret", opener=opener).fetch_unrate("2024-01-01", "2024-02-01")
        self.assertEqual(len(pages), 2)
        query = parse_qs(urlparse(opener.call_args_list[1].args[0]).query)
        self.assertEqual(query["series_id"], ["UNRATE"])
        self.assertEqual(query["offset"], ["1"])
        self.assertEqual(query["observation_end"], ["2024-02-01"])
        self.assertEqual(query["file_type"], ["json"])
        self.assertEqual(opener.call_args.kwargs["timeout"], 30)

    def test_transient_failures_retry(self):
        for status in [429, 503]:
            sleep = Mock()
            opener = Mock(side_effect=[HTTPError("secret-url", status, "error", {}, io.BytesIO()),
                                       response(page([]))])
            self.assertEqual(FredClient("key", opener=opener, sleeper=sleep)
                             .fetch_unrate("2024-01-01"), [page([])])
            sleep.assert_called_once_with(1)

    def test_retries_are_bounded_and_errors_sanitized(self):
        opener = Mock(side_effect=URLError("test-secret in URL"))
        with self.assertRaises(IngestionError) as caught:
            FredClient("test-secret", opener=opener, sleeper=Mock()).fetch_unrate("2024-01-01")
        self.assertEqual(opener.call_count, 3)
        self.assertNotIn("test-secret", str(caught.exception))

    def test_auth_failure_does_not_retry(self):
        opener = Mock(side_effect=HTTPError("test-secret", 400, "test-secret", {}, io.BytesIO()))
        with self.assertRaises(IngestionError) as caught:
            FredClient("test-secret", opener=opener).fetch_unrate("2024-01-01")
        self.assertEqual(opener.call_count, 1)
        self.assertNotIn("test-secret", str(caught.exception))

    def test_malformed_response_and_incomplete_pages(self):
        payloads = [[], {"error_code": 400}, page([], 1), page([row()], 0),
                    page([], offset=1), {"count": 1, "offset": 0}]
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(IngestionError):
                FredClient("key", opener=Mock(return_value=response(payload))).fetch_unrate("2024-01-01")
        with self.assertRaises(IngestionError):
            FredClient("key", opener=Mock(return_value=io.StringIO("invalid"))).fetch_unrate("2024-01-01")


class IngestionTests(unittest.TestCase):
    def test_normalization_orders_and_preserves_missing(self):
        rows = normalize([page([row("2024-02-01", "."), row()])], "2024-01-01", None)
        self.assertEqual([r["date"] for r in rows], ["2024-01-01", "2024-02-01"])
        self.assertEqual(rows[0]["value"], 3.7)
        self.assertIsNone(rows[1]["value"])
        self.assertEqual(rows[0]["realtime_start"], "2024-03-01")

    def test_invalid_values_dates_and_duplicates_rejected(self):
        bad_rows = [[row(value=v)] for v in ["nan", "inf", "oops", "-1", "101"]]
        bad_rows += [[row(), row()], [row("2023-01-01")], [row("invalid")], [{}]]
        for rows in bad_rows:
            with self.subTest(rows=rows), self.assertRaises(IngestionError):
                normalize([page(rows)], "2024-01-01", "2024-02-01")

    def test_repeat_ingestion_refreshes_and_archives(self):
        client = Mock()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client.fetch_unrate.return_value = [page([row()])]
            first = ingest_unrate(client, root, "2024-01-01")
            client.fetch_unrate.return_value = [page([row(value="3.8")])]
            second = ingest_unrate(client, root, "2024-01-01")
            snapshot = json.loads(Path(second["processed_path"]).read_text())
            self.assertEqual(len(snapshot["observations"]), 1)
            self.assertEqual(snapshot["observations"][0]["value"], 3.8)
            self.assertTrue(Path(first["raw_path"]).exists())
            self.assertNotEqual(first["raw_path"], second["raw_path"])
            self.assertEqual(len(list(root.glob("raw/fred/UNRATE/*.json"))), 2)

    def test_failed_fetch_or_validation_preserves_snapshot(self):
        client = Mock()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client.fetch_unrate.return_value = [page([row()])]
            result = ingest_unrate(client, root, "2024-01-01")
            path = Path(result["processed_path"])
            original = path.read_bytes()
            client.fetch_unrate.side_effect = IngestionError("Unavailable")
            with self.assertRaises(IngestionError):
                ingest_unrate(client, root, "2024-01-01")
            client.fetch_unrate.side_effect = None
            client.fetch_unrate.return_value = [page([row(value="nan")])]
            with self.assertRaises(IngestionError):
                ingest_unrate(client, root, "2024-01-01")
            self.assertEqual(path.read_bytes(), original)

    def test_cli_missing_key(self):
        with patch.dict("os.environ", {"FRED_API_KEY": ""}), patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(main(["ingest-unrate"]), 1)
            self.assertIn("Set FRED_API_KEY", stderr.getvalue())

    def test_lambda_defaults_to_ephemeral_storage(self):
        with patch.dict("os.environ", {"FRED_API_KEY": "key"}, clear=True), \
             patch("economic_dashboard.lambda_handler.ingest_unrate") as ingest:
            handler({"source": "aws.events"}, None)
            self.assertEqual(ingest.call_args.args[1], Path("/tmp/economic-dashboard"))


if __name__ == "__main__":
    unittest.main()
