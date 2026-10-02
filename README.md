# U.S. Economic Intelligence Dashboard

A portfolio project for understanding national U.S. economic conditions across growth, inflation, labor, interest rates, and fiscal health using FRED and U.S. Treasury Fiscal Data.

## Current status

The project foundation and first Python ingestion feature are implemented locally. The first vertical slice targets FRED `UNRATE`: fetch observations, retain raw responses, normalize data, and eventually display an unemployment-rate chart. The chart, web API, database, and AWS infrastructure are planned; no AWS resources have been deployed.

## Local setup

Requires Python 3.11 or newer. The initial backend uses the standard library and has no runtime dependencies.

```sh
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
```

Get a [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) and set `FRED_API_KEY` in `.env`. Keep the key on the backend. Load the trusted local environment file, then run from the repository root:

```sh
set -a
source .env
set +a
PYTHONPATH=backend/src python -m economic_dashboard ingest-unrate --start 2000-01-01
```

`.env` is not loaded automatically. An exported environment variable works too. Optional `--end YYYY-MM-DD` bounds the requested interval. Defaults are configured through `.env.example`.

If a python.org macOS installation reports a TLS certificate verification failure, run `Install Certificates.command` from its Python folder in `/Applications` (for example, `/Applications/Python 3.11/Install Certificates.command`) and retry. This installs the certificate bundle used by that Python installation, including virtual environments based on it. See [Python's macOS setup instructions](https://docs.python.org/3/using/mac.html).

Generated files under `data/local/` are ignored by Git:

- `raw/fred/UNRATE/<run-id>.json`: original response pages plus retrieval provenance (no API key).
- `processed/UNRATE.json`: latest normalized snapshot, ordered by observation date; missing values are `null`.

Re-running refreshes the snapshot rather than appending duplicate observations. FRED revisions replace previously retrieved values; this is a latest-data view, not a historical vintage database. A failed request or invalid response leaves the existing processed snapshot intact.

Run the offline test suite:

```sh
PYTHONPATH=backend/src python -m unittest discover -s backend/tests -v
```

## Repository layout

```text
backend/src/economic_dashboard/  FRED client, normalization, local storage, CLI, Lambda entry point
backend/tests/                  Offline ingestion tests
data/indicators.yaml            Indicator catalog and implementation status
docs/MVP.md                     Scope, milestones, and acceptance criteria
docs/ARCHITECTURE.md            Local design and planned AWS architecture
```

Planned stack: React, TypeScript, Vite, Tailwind; Python backend and analytics; AWS Lambda, EventBridge, S3, CloudFront, Aurora DSQL; Terraform and GitHub Actions.

See [MVP scope](docs/MVP.md) and [architecture](docs/ARCHITECTURE.md). Source references: [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [UNRATE metadata](https://fred.stlouisfed.org/series/UNRATE), and [Treasury Fiscal Data API](https://fiscaldata.treasury.gov/api-documentation/).
