"""Implemented series contracts; planned catalog entries are not executable."""

RAW_SERIES = {
    "UNRATE": {"title": "Unemployment Rate", "units": "Percent"},
    "CPIAUCSL": {
        "title": "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
        "units": "Index 1982-1984=100",
    },
}
INFLATION_ID = "CPIAUCSL_YOY"
INFLATION_FORMULA = "(CPI this month / CPI in the same month one year earlier - 1) * 100"


def metadata(series_id: str) -> dict:
    source_id = "CPIAUCSL" if series_id == INFLATION_ID else series_id
    if source_id not in RAW_SERIES:
        raise ValueError("Unsupported series.")
    fields = RAW_SERIES[source_id] if series_id != INFLATION_ID else {
        "title": "CPI inflation, year over year", "units": "Percent",
        "source_series_id": source_id,
        "transformation": {"kind": "year_over_year", "lag_months": 12,
                           "formula": INFLATION_FORMULA},
    }
    return {"series_id": series_id, "source": "FRED", **fields,
            "source_url": f"https://fred.stlouisfed.org/series/{source_id}",
            "frequency": "Monthly", "seasonal_adjustment": "Seasonally Adjusted"}
