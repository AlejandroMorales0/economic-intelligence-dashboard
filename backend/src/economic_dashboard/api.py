"""Local read-only HTTP API backed by the processed snapshot, never by FRED."""

import json
from datetime import datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .fred import IngestionError, validate_range
from .ingestion import normalize
from .catalog import RAW_SERIES, INFLATION_ID, metadata
from .analytics import cpi_lookback_start, inflation_yoy


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def read_series(data_dir: Path, start: str | None = None,
                end: str | None = None, series_id: str = "UNRATE") -> dict:
    if series_id not in {*RAW_SERIES, INFLATION_ID}:
        raise ApiError(404, "not_found", "Unknown series.")
    source_id = "CPIAUCSL" if series_id == INFLATION_ID else series_id
    try:
        validate_range(start or "0001-01-01", end)
    except IngestionError as error:
        raise ApiError(400, "invalid_date_range", str(error)) from None
    try:
        snapshot = json.loads((data_dir / "processed" / f"{source_id}.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        command = "ingest-cpi" if source_id == "CPIAUCSL" else "ingest-unrate"
        raise ApiError(404, "data_not_found", f"No saved {source_id} data. Run {command} first.") from None
    except (OSError, ValueError, UnicodeError):
        raise ApiError(503, "invalid_snapshot", f"Saved {source_id} data is unreadable. Run ingestion again.") from None
    try:
        if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
            raise ValueError
        expected = metadata(source_id)
        if any(snapshot.get(key) != value for key, value in expected.items()):
            raise ValueError
        if not isinstance(snapshot.get("title"), str) or not snapshot["title"]:
            raise ValueError
        retrieved = datetime.fromisoformat(snapshot["retrieved_at"])
        if retrieved.tzinfo is None:
            raise ValueError
        stored_rows = snapshot["observations"]
        if not isinstance(stored_rows, list) or any(
            not isinstance(row, dict) or (row.get("value") is not None and
            type(row.get("value")) not in (int, float)) for row in stored_rows
        ):
            raise ValueError
        # The raw normalizer expects FRED's '.', while stored missing values are null.
        raw_rows = [{**row, "value": "." if row["value"] is None else str(row["value"])}
                    for row in stored_rows]
        rows = normalize([{"observations": raw_rows}], "0001-01-01", None, source_id)
        if source_id == "CPIAUCSL":
            display_start = snapshot["display_start"]
            validate_range(display_start, snapshot["requested_end"])
            if snapshot["requested_start"] != cpi_lookback_start(display_start):
                raise ValueError
            if any(row["date"] < snapshot["requested_start"] or
                   (snapshot["requested_end"] and row["date"] > snapshot["requested_end"]) for row in rows):
                raise ValueError
            if series_id == INFLATION_ID:
                rows = inflation_yoy(rows, display_start, snapshot["requested_end"])
    except (ValueError, KeyError, TypeError):
        raise ApiError(503, "invalid_snapshot", f"Saved {source_id} data is invalid. Run ingestion again.") from None
    filtered = [row for row in rows if (not start or row["date"] >= start)
                and (not end or row["date"] <= end)]
    # Explicit fields keep internal paths and future private metadata out of the API.
    return {
        "schema_version": 1, **metadata(series_id),
        "retrieved_at": snapshot["retrieved_at"],
        "available_start": rows[0]["date"] if rows else None,
        "available_end": rows[-1]["date"] if rows else None,
        "filters": {"start": start, "end": end},
        "observation_count": len(filtered), "observations": filtered,
    }


def dispatch(data_dir: Path, target: str) -> tuple[int, dict]:
    parsed = urlsplit(target)
    if parsed.path == "/api/health":
        return 200, {"status": "ok"}
    routes = {f"/api/series/{series_id}": series_id for series_id in [*RAW_SERIES, INFLATION_ID]}
    if parsed.path not in routes:
        return 404, {"error": {"code": "not_found", "message": "Unknown API route."}}
    try:
        query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=10)
        if any(key not in {"start", "end"} or len(values) != 1 or not values[0]
               for key, values in query.items()):
            raise ValueError
    except ValueError:
        return 400, {"error": {"code": "invalid_query", "message": "Use one nonempty start and/or end date only."}}
    try:
        return 200, read_series(data_dir, query.get("start", [None])[0], query.get("end", [None])[0], routes[parsed.path])
    except ApiError as error:
        return error.status, {"error": {"code": error.code, "message": error.message}}


class ApiHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, data_dir: Path, **kwargs):
        self.data_dir = data_dir
        super().__init__(*args, **kwargs)

    def do_GET(self):
        status, payload = dispatch(self.data_dir, self.path)
        self._reply(status, payload)

    def do_POST(self):
        self._reply(405, {"error": {"code": "method_not_allowed", "message": "This API is read-only."}})

    def _reply(self, status: int, payload: dict):
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 405:
            self.send_header("Allow", "GET")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Do not log user-supplied query strings.
        pass


def serve(data_dir: Path, port: int = 8000) -> None:
    # Standard-library server for local development, not production deployment.
    with ThreadingHTTPServer(("127.0.0.1", port), partial(ApiHandler, data_dir=data_dir)) as server:
        print(f"Read API listening on http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nRead API stopped.")
