# U.S. Economic Intelligence Dashboard

A portfolio project for understanding national U.S. economic conditions across growth, inflation, labor, interest rates, and fiscal health using FRED and U.S. Treasury Fiscal Data.

## Current status

Two vertical slices work locally: unemployment (`UNRATE`) and CPI inflation derived from `CPIAUCSL`. Both retain raw responses, normalize data, serve stored observations through a Python read API, and display interactive React charts. The database and AWS infrastructure remain planned; no AWS resources have been deployed.

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

## Ingest CPI and calculate inflation

After loading `.env` as above, run from the repository root:

```sh
PYTHONPATH=backend/src python -m economic_dashboard ingest-cpi --start 2000-01-01
```

The reusable command `ingest --series CPIAUCSL --start 2000-01-01` does the same job; `ingest --series UNRATE` supports unemployment too. Existing `ingest-unrate` commands continue to work.

CPI ingestion automatically fetches from January 1999 for a January 2000 display start. The raw archive is under `data/local/raw/fred/CPIAUCSL/`; the normalized original-unit index is stored in `data/local/processed/CPIAUCSL.json`, including the lookback. `requested_start` records the actual fetch start; `display_start` records the requested chart start. Optional `--end` remains inclusive.

The read API computes `CPIAUCSL_YOY` from that single CPI snapshot before applying API date filters:

```text
Inflation (%) = (CPI this month / CPI in the same month one year earlier - 1) × 100
```

The calculation matches dates, not row positions. Missing current/prior observations produce `null`; an absent current month inside the display period is represented as a null observation to keep a chart gap. CPI values must be positive; inflation can be negative. The derived series keeps full precision until display, which rounds to one decimal place. A derived snapshot is not independently persisted, so its values and source index cannot drift between refreshes.

`CPIAUCSL` is seasonally adjusted, monthly, and measured in Index 1982-1984=100. This derived rate can differ from the commonly reported headline rate based on unadjusted CPI. See [FRED's CPI metadata](https://fred.stlouisfed.org/series/CPIAUCSL).

## Run the dashboard

Use Node.js 22 LTS (22.12+) or 24 LTS and npm in addition to Python. Check `node --version` and select your current Node installation before running npm; older system installations will not run Vite. From the repository root, start the read API in one terminal:

```sh
source .venv/bin/activate
PYTHONPATH=backend/src python -m economic_dashboard serve
```

In a second terminal, start the frontend:

```sh
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. The API listens on `127.0.0.1:8000`; Vite proxies `/api` to it. Both servers bind to loopback for local use. Run all backend commands from the repository root so the default `data/local` path resolves correctly. If ingestion uses another data directory, pass the same directory with `serve --data-dir PATH` (or load `.env` in that terminal).

Use the **Dark mode / Light mode** button in the header to switch themes. The initial theme follows your device preference, and an explicit selection is remembered in this browser. Both charts, tooltips, tables, and date controls follow the selected theme.

The home page shows **Unemployment** and **Inflation** tiles, each with its latest numeric rate, up to five years of chart history, source, and retrieval date. Click a tile (or focus it and press Enter) to open its large chart with date filters, methodology, and an observation table. **Back to overview** returns to the tiles and restores keyboard focus. Detail views also have **Labor** and **Inflation** tabs (arrow keys switch tabs). The two series load independently and remain cached when navigating, so a missing snapshot does not hide the other tile.

The read API needs no FRED key. Each view shows saved data only: run ingestion again, then click **Reload saved data** to see a new snapshot. On the overview, reload refreshes both tiles; in a detail view, it refreshes that series only. Reload does not fetch FRED. Date presets end at the latest saved observation; custom date filters are inclusive. The latest-rate card and observation table follow the selected range. Retrieval time and overall dataset coverage describe the saved snapshot and remain visible across filters. Missing values stay null and break the chart line. Switching domains resets date filters to that domain's available range. A missing CPI snapshot prompts you to run `ingest-cpi` and leaves Labor available.

Read API routes:

- `GET /api/health`: server health (does not imply data availability).
- `GET /api/series/UNRATE`: metadata and saved observations.
- `GET /api/series/UNRATE?start=2020-01-01&end=2024-12-31`: inclusive date filtering.
- `GET /api/series/CPIAUCSL`: original-unit CPI index, including the stored lookback.
- `GET /api/series/CPIAUCSL_YOY`: separately labeled derived inflation with its formula and source-series identity.

All series routes accept the same optional `start` and `end` filters. `CPIAUCSL_YOY` is a local identifier, not a FRED series ID. Its source link points to CPIAUCSL. The API validates the stored CPI snapshot and computes the derived series on each read; it never calls FRED.

Errors return JSON with an `error.code` and `error.message`: invalid queries return 400, missing snapshots or routes return 404, and corrupt/unreadable snapshots return 503. There are no ingestion or filesystem browsing endpoints. The standard-library HTTP server is for local development; a production API adapter is a later milestone.

## Verification

Run the offline test suite:

```sh
PYTHONPATH=backend/src python -m unittest discover -s backend/tests -v
```

Frontend tests and production build:

```sh
cd frontend
npm test
npm run build
```

`npm run preview` serves the build at the same frontend address and proxies to the running read API. The deployed frontend/API boundary will be configured in a later infrastructure phase. Frontend tests use synthetic fixtures; the running app always uses the saved API snapshot.

`frontend/.npmrc` avoids an npm 9/11 crash when resolving optional Vitest browser-provider peers. Required runtime and test dependencies are declared explicitly; keep this setting when regenerating the lockfile or running `npm ci`.

## Repository layout

```text
backend/src/economic_dashboard/  Catalog, ingestion, analytics, read API, CLI, Lambda entry point
backend/tests/                  Offline ingestion and API tests
frontend/                      React, TypeScript, Vite, Tailwind, Recharts
data/indicators.yaml            Indicator catalog and implementation status
docs/MVP.md                     Scope, milestones, and acceptance criteria
docs/ARCHITECTURE.md            Local design and planned AWS architecture
```

Implemented stack: React, TypeScript, Vite, Tailwind, Recharts, and Python. Planned: additional analytics; AWS Lambda, EventBridge, S3, CloudFront, Aurora DSQL; Terraform and GitHub Actions.

See [MVP scope](docs/MVP.md) and [architecture](docs/ARCHITECTURE.md). Source references: [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [UNRATE metadata](https://fred.stlouisfed.org/series/UNRATE), and [Treasury Fiscal Data API](https://fiscaldata.treasury.gov/api-documentation/).
