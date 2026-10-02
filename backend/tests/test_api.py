import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from economic_dashboard.api import dispatch
from economic_dashboard.ingestion import ingest_unrate
from test_ingestion import page, row


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def seed(self):
        with patch("economic_dashboard.fred.FredClient") as client:
            client.fetch_unrate.return_value = [page([row(), row("2024-02-01", "."),
                                                    row("2024-03-01", "3.8")])]
            ingest_unrate(client, self.root, "2024-01-01")

    def test_health_and_missing_data(self):
        self.assertEqual(dispatch(self.root, "/api/health"), (200, {"status": "ok"}))
        status, body = dispatch(self.root, "/api/series/UNRATE")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "data_not_found")

    def test_ingestion_to_api_and_inclusive_filter(self):
        self.seed()
        with patch("economic_dashboard.fred.FredClient.fetch_unrate", side_effect=AssertionError("Network forbidden")):
            status, data = dispatch(self.root, "/api/series/UNRATE?start=2024-02-01&end=2024-03-01")
        self.assertEqual(status, 200)
        self.assertEqual(data["observation_count"], 2)
        self.assertIsNone(data["observations"][0]["value"])
        self.assertEqual(data["observations"][1]["value"], 3.8)
        self.assertEqual(data["available_start"], "2024-01-01")
        self.assertNotIn("run_id", data)

    def test_empty_range(self):
        self.seed()
        status, data = dispatch(self.root, "/api/series/UNRATE?start=2025-01-01")
        self.assertEqual(status, 200)
        self.assertEqual(data["observations"], [])

    def test_bad_dates_queries_and_routes(self):
        for query in ["start=bad", "start=2024-02-30", "start=2025-01-01&end=2024-01-01",
                      "start=", "start=2024-01-01&start=2024-02-01", "api_key=secret"]:
            with self.subTest(query=query):
                self.assertEqual(dispatch(self.root, "/api/series/UNRATE?" + query)[0], 400)
        self.assertEqual(dispatch(self.root, "/api/series/OTHER")[0], 404)
        self.assertEqual(dispatch(self.root, "/../../.env")[0], 404)

    def test_corrupt_snapshot(self):
        self.seed()
        path = self.root / "processed" / "UNRATE.json"
        original = json.loads(path.read_text())
        for payload in ["broken", [], {**original, "units": "Dollars"},
                        {**original, "retrieved_at": "invalid"},
                        {**original, "observations": [row(value="nan")]}]:
            path.write_text(payload if isinstance(payload, str) else json.dumps(payload))
            self.assertEqual(dispatch(self.root, "/api/series/UNRATE")[0], 503)

    def test_rereads_updated_snapshot(self):
        self.seed()
        path = self.root / "processed" / "UNRATE.json"
        snapshot = json.loads(path.read_text())
        snapshot["observations"][0]["value"] = 4.0
        path.write_text(json.dumps(snapshot))
        self.assertEqual(dispatch(self.root, "/api/series/UNRATE")[1]["observations"][0]["value"], 4.0)
