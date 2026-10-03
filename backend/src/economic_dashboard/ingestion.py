"""Normalize implemented FRED series and publish local snapshots."""

import json
import math
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from .fred import FredClient, IngestionError, validate_range
from .catalog import RAW_SERIES, metadata
from .analytics import cpi_lookback_start, inflation_yoy


def normalize(pages: list[dict], start: str, end: str | None,
              series_id: str = "UNRATE") -> list[dict]:
    validate_range(start, end)
    if series_id not in RAW_SERIES:
        raise IngestionError("Unsupported FRED series.")
    observations = {}
    try:
        for page in pages:
            for row in page["observations"]:
                period = date.fromisoformat(row["date"]).isoformat()
                if period != row["date"] or date.fromisoformat(period).day != 1 or period < start or (end and period > end):
                    raise ValueError
                value = None if row["value"] == "." else float(row["value"])
                valid_value = value is None or (math.isfinite(value) and
                    (0 <= value <= 100 if series_id == "UNRATE" else value > 0))
                if not valid_value:
                    raise ValueError
                realtime_start = date.fromisoformat(row["realtime_start"]).isoformat()
                realtime_end = date.fromisoformat(row["realtime_end"]).isoformat()
                if realtime_start > realtime_end or period in observations:
                    raise ValueError
                observations[period] = {
                    "date": period, "value": value,
                    "realtime_start": realtime_start, "realtime_end": realtime_end,
                }
    except (KeyError, TypeError, ValueError, OverflowError):
        raise IngestionError("FRED observations contain invalid or duplicate data.") from None
    return [observations[key] for key in sorted(observations)]


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def ingest_unrate(client: FredClient, data_dir: Path, start: str,
                  end: str | None = None) -> dict:
    validate_range(start, end)
    pages = client.fetch_unrate(start, end)
    return _publish(pages, data_dir, "UNRATE", start, start, end)


def ingest_series(client: FredClient, data_dir: Path, series_id: str,
                  start: str, end: str | None = None) -> dict:
    if series_id == "UNRATE":
        return ingest_unrate(client, data_dir, start, end)
    if series_id not in RAW_SERIES:
        raise IngestionError("Unsupported FRED series.")
    validate_range(start, end)
    fetch_start = cpi_lookback_start(start)
    pages = client.fetch_series(series_id, fetch_start, end)
    return _publish(pages, data_dir, series_id, fetch_start, start, end)


def _publish(pages: list[dict], data_dir: Path, series_id: str,
             fetch_start: str, display_start: str, end: str | None) -> dict:
    observations = normalize(pages, fetch_start, end, series_id)
    # Validate analytics before any writes; the API derives from this same snapshot.
    if series_id == "CPIAUCSL":
        inflation_yoy(observations, display_start, end)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    run_id = uuid4().hex
    provenance = {
        "schema_version": 1, **metadata(series_id),
        "retrieved_at": retrieved_at, "requested_start": fetch_start, "requested_end": end,
        "display_start": display_start,
    }
    raw_path = data_dir / "raw" / "fred" / series_id / f"{run_id}.json"
    processed_path = data_dir / "processed" / f"{series_id}.json"
    write_json_atomic(raw_path, {**provenance, "run_id": run_id, "pages": pages})
    write_json_atomic(processed_path, {
        **provenance, "run_id": run_id, "observations": observations,
    })
    return {"series_id": series_id, "observation_count": len(observations),
            "raw_path": str(raw_path), "processed_path": str(processed_path),
            "retrieved_at": retrieved_at}
