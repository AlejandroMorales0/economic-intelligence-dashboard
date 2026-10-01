"""Handler scaffold with ephemeral storage; no deployed AWS resources."""

import os
from pathlib import Path

from .fred import FredClient
from .ingestion import ingest_unrate


def handler(event, context):
    # EventBridge envelopes are ignored. Use a trusted configured date range.
    return ingest_unrate(
        FredClient(os.getenv("FRED_API_KEY", "")),
        Path(os.getenv("DATA_DIR", "/tmp/economic-dashboard")),
        os.getenv("FRED_OBSERVATION_START", "2000-01-01"),
    )
