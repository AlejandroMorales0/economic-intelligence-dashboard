"""Calendar-aligned analytics using stored original-unit observations."""

import math
from datetime import date

from .fred import IngestionError, validate_range


def cpi_lookback_start(start: str) -> str:
    validate_range(start, None)
    period = date.fromisoformat(start)
    if period.year < 2:
        raise IngestionError("CPI ingestion needs a start year of at least 0002 for its 12-month lookback.")
    return date(period.year - 1, period.month, 1).isoformat()


def inflation_yoy(rows: list[dict], start: str, end: str | None = None) -> list[dict]:
    """Emit a monthly spine. Missing current/prior values produce null, never zero."""
    validate_range(start, end)
    if not rows:
        return []
    by_date = {row["date"]: row for row in rows}
    first = date.fromisoformat(start)
    period = date(first.year, first.month, 1)
    last = min(rows[-1]["date"], end) if end else rows[-1]["date"]
    result = []
    while period.isoformat() <= last:
        key = period.isoformat()
        if key >= start:
            current = by_date.get(key)
            prior = by_date.get(date(period.year - 1, period.month, 1).isoformat()) if period.year > 1 else None
            value = None
            if current and prior and current["value"] is not None and prior["value"] is not None:
                if current["value"] <= 0 or prior["value"] <= 0:
                    raise IngestionError("CPI values must be positive to calculate inflation.")
                value = (current["value"] / prior["value"] - 1) * 100
                if not math.isfinite(value) or value <= -100:
                    raise IngestionError("Calculated inflation exceeds numeric precision limits.")
            result.append({"date": key, "value": value,
                           "realtime_start": current["realtime_start"] if current else None,
                           "realtime_end": current["realtime_end"] if current else None})
        if period.year == 9999 and period.month == 12:
            break
        period = date(period.year + (period.month == 12), period.month % 12 + 1, 1)
    return result
