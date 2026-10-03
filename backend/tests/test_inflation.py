import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from economic_dashboard.analytics import cpi_lookback_start, inflation_yoy
from economic_dashboard.api import dispatch
from economic_dashboard.cli import main
from economic_dashboard.fred import FredClient, IngestionError
from economic_dashboard.ingestion import ingest_series, normalize
from test_ingestion import page, response, row


class InflationTests(unittest.TestCase):
    def normalized(self, rows):
        return normalize([page(rows)], "2020-01-01", None, "CPIAUCSL")

    def test_calendar_lookback_handles_leap_days_and_midmonth(self):
        self.assertEqual(cpi_lookback_start("2024-02-29"), "2023-02-01")
        self.assertEqual(cpi_lookback_start("2000-01-01"), "1999-01-01")
        with self.assertRaises(IngestionError):
            cpi_lookback_start("0001-01-01")

    def test_known_percent_change_and_deflation(self):
        rows = self.normalized([row("2023-01-01", "200"), row("2023-02-01", "200"),
                                row("2024-01-01", "210"), row("2024-02-01", "190")])
        result = inflation_yoy(rows, "2024-01-01")
        self.assertAlmostEqual(result[0]["value"], 5)
        self.assertAlmostEqual(result[1]["value"], -5)

    def test_calendar_alignment_does_not_use_twelfth_previous_row(self):
        rows = self.normalized([row("2023-02-01", "200"), row("2024-01-01", "210")])
        self.assertIsNone(inflation_yoy(rows, "2024-01-01")[0]["value"])

    def test_absent_months_and_null_inputs_remain_gaps(self):
        rows = self.normalized([row("2023-01-01", "200"), row("2023-02-01", "."),
                                row("2023-03-01", "200"), row("2024-01-01", "210"),
                                row("2024-03-01", "."), row("2024-04-01", "211")])
        result = inflation_yoy(rows, "2024-01-01")
        self.assertEqual([r["date"] for r in result], ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"])
        self.assertEqual([r["value"] for r in result[1:]], [None, None, None])
        self.assertIsNone(result[1]["realtime_start"])

    def test_missing_prior_value_and_midmonth_range(self):
        rows = self.normalized([row("2023-02-01", "."), row("2024-01-01", "210"), row("2024-02-01", "211")])
        result = inflation_yoy(rows, "2024-01-15", "2024-02-01")
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["value"])
        self.assertEqual(inflation_yoy([], "2024-01-01"), [])

    def test_cpi_domain_and_nonfinite_calculation(self):
        self.assertEqual(self.normalized([row("2024-01-01", "310.25")])[0]["value"], 310.25)
        for value in ["0", "-1", "nan", "inf"]:
            with self.subTest(value=value), self.assertRaises(IngestionError):
                self.normalized([row("2024-01-01", value)])
        with self.assertRaises(IngestionError):
            inflation_yoy(self.normalized([row("2023-01-01", "1e-300"), row("2024-01-01", "1e300")]), "2024-01-01")
        with self.assertRaises(IngestionError):
            inflation_yoy(self.normalized([row("2023-01-01", "1e300"), row("2024-01-01", "1e-300")]), "2024-01-01")
        with self.assertRaises(IngestionError):
            self.normalized([row("2024-01-15", "310")])

    def test_cpi_http_request_uses_original_units(self):
        opener = Mock(return_value=response(page([])))
        FredClient("key", opener=opener).fetch_series("CPIAUCSL", "2023-01-01")
        query = parse_qs(urlparse(opener.call_args.args[0]).query)
        self.assertEqual(query["series_id"], ["CPIAUCSL"])
        self.assertEqual(query["units"], ["lin"])
        self.assertNotIn("frequency", query)

    def test_ingestion_to_inflation_api_with_lookback_and_filter(self):
        client = Mock()
        client.fetch_series.return_value = [page([row("2023-01-01", "200"), row("2023-02-01", "200"),
                                                row("2024-01-01", "210"), row("2024-02-01", "190")])]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = ingest_series(client, root, "CPIAUCSL", "2024-01-01", "2024-02-01")
            client.fetch_series.assert_called_once_with("CPIAUCSL", "2023-01-01", "2024-02-01")
            stored = json.loads(Path(result["processed_path"]).read_text())
            self.assertEqual(stored["units"], "Index 1982-1984=100")
            self.assertEqual(stored["observations"][0]["value"], 200)
            self.assertEqual(stored["display_start"], "2024-01-01")
            with patch("economic_dashboard.fred.FredClient.fetch_series", side_effect=AssertionError("No network")):
                status, data = dispatch(root, "/api/series/CPIAUCSL_YOY?start=2024-02-01&end=2024-02-01")
            self.assertEqual(status, 200)
            self.assertEqual(data["observation_count"], 1)
            self.assertAlmostEqual(data["observations"][0]["value"], -5)
            self.assertEqual(data["source_series_id"], "CPIAUCSL")
            self.assertEqual(data["transformation"]["lag_months"], 12)
            self.assertEqual(data["available_start"], "2024-01-01")
            self.assertEqual(dispatch(root, "/api/series/CPIAUCSL")[1]["observations"][0]["value"], 200)
            self.assertEqual(dispatch(root, "/api/series/CPIAUCSL_YOY?start=2025-01-01")[1]["observations"], [])

    def test_missing_corrupt_and_failed_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(dispatch(root, "/api/series/CPIAUCSL_YOY")[0], 404)
            client = Mock()
            client.fetch_series.return_value = [page([row("2023-01-01", "200"), row("2024-01-01", "210")])]
            result = ingest_series(client, root, "CPIAUCSL", "2024-01-01")
            path = Path(result["processed_path"])
            original = path.read_bytes()
            client.fetch_series.return_value = [page([row("2024-01-01", "0")])]
            with self.assertRaises(IngestionError):
                ingest_series(client, root, "CPIAUCSL", "2024-01-01")
            self.assertEqual(path.read_bytes(), original)
            saved = json.loads(original)
            saved["display_start"] = "2025-01-01"
            path.write_text(json.dumps(saved))
            self.assertEqual(dispatch(root, "/api/series/CPIAUCSL_YOY")[0], 503)

    def test_cli_shortcut_and_generic_command(self):
        for command in [["ingest-cpi"], ["ingest", "--series", "CPIAUCSL"]]:
            with patch.dict("os.environ", {"FRED_API_KEY": "key"}), \
                 patch("economic_dashboard.cli.ingest_series", return_value={}) as ingest, \
                 patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main(command + ["--start", "2024-01-01"]), 0)
                self.assertEqual(ingest.call_args.args[2], "CPIAUCSL")
