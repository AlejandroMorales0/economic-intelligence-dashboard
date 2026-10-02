import argparse
import json
import os
import sys
from pathlib import Path

from .api import serve
from .fred import FredClient, IngestionError, validate_range
from .ingestion import ingest_unrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Economic dashboard local ingestion")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("ingest-unrate", help="Fetch and store FRED UNRATE")
    command.add_argument("--start", default=os.getenv("FRED_OBSERVATION_START", "2000-01-01"))
    command.add_argument("--end", default=None)
    command.add_argument("--data-dir", type=Path, default=Path(os.getenv("DATA_DIR", "data/local")))
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
        result = ingest_unrate(FredClient(os.getenv("FRED_API_KEY", "")),
                               args.data_dir, args.start, args.end)
    except IngestionError as error:
        print(f"Ingestion failed: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("Ingestion failed: unable to write local data; check directory permissions.",
              file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
