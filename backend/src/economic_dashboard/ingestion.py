"""Normalize UNRATE and publish local snapshots."""

import json
import math
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from .fred import FredClient, IngestionError, validate_range


def normalize(pages: list[dict], start: str, end: str | None) -> list[dict]:
    validate_range(start, end)
    observations = {}
    try:
        for page in pages:
            for row in page["observations"]:
                period = date.fromisoformat(row["date"]).isoformat()
                if period != row["date"] or period < start or (end and period > end):
                    raise ValueError
                value = None if row["value"] == "." else float(row["value"])
                if value is not None and (not math.isfinite(value) or not 0 <= value <= 100):
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
    observations = normalize(pages, start, end)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    run_id = uuid4().hex
    provenance = {
        "schema_version": 1, "series_id": "UNRATE", "source": "FRED",
        "source_url": "https://fred.stlouisfed.org/series/UNRATE",
        "retrieved_at": retrieved_at, "requested_start": start, "requested_end": end,
    }
    raw_path = data_dir / "raw" / "fred" / "UNRATE" / f"{run_id}.json"
    processed_path = data_dir / "processed" / "UNRATE.json"
    write_json_atomic(raw_path, {**provenance, "run_id": run_id, "pages": pages})
    write_json_atomic(processed_path, {
        **provenance, "run_id": run_id, "title": "Unemployment Rate",
        "units": "Percent", "frequency": "Monthly",
        "seasonal_adjustment": "Seasonally Adjusted", "observations": observations,
    })
    return {"series_id": "UNRATE", "observation_count": len(observations),
            "raw_path": str(raw_path), "processed_path": str(processed_path),
            "retrieved_at": retrieved_at}
