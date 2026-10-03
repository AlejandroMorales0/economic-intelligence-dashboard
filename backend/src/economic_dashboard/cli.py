import argparse
import json
import os
import sys
from pathlib import Path

from .api import serve
from .fred import FredClient, IngestionError, validate_range
from .ingestion import ingest_series
from .catalog import RAW_SERIES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Economic dashboard local ingestion")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, description in [("ingest-unrate", "Fetch and store FRED UNRATE"),
                              ("ingest-cpi", "Fetch CPI with a 12-month inflation lookback"),
                              ("ingest", "Fetch an implemented FRED series")]:
        command = commands.add_parser(name, help=description)
        command.add_argument("--start", default=os.getenv("FRED_OBSERVATION_START", "2000-01-01"))
        command.add_argument("--end", default=None)
        command.add_argument("--data-dir", type=Path, default=Path(os.getenv("DATA_DIR", "data/local")))
        if name == "ingest":
            command.add_argument("--series", required=True, choices=sorted(RAW_SERIES))
    server = commands.add_parser("serve", help="Serve locally saved data over HTTP")
    server.add_argument("--port", type=int, default=8000)
    server.add_argument("--data-dir", type=Path, default=Path(os.getenv("DATA_DIR", "data/local")))
    args = parser.parse_args(argv)
    if args.command == "serve":
        if not 1 <= args.port <= 65535:
            parser.error("--port must be between 1 and 65535")
        try:
            serve(args.data_dir, args.port)
        except OSError:
            print("Unable to start read API; check port availability and permissions.", file=sys.stderr)
            return 1
        return 0
    try:
        validate_range(args.start, args.end)
        series_id = args.series if args.command == "ingest" else (
            "CPIAUCSL" if args.command == "ingest-cpi" else "UNRATE")
        result = ingest_series(FredClient(os.getenv("FRED_API_KEY", "")),
                               args.data_dir, series_id, args.start, args.end)
    except IngestionError as error:
        print(f"Ingestion failed: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("Ingestion failed: unable to write local data; check directory permissions.",
              file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
