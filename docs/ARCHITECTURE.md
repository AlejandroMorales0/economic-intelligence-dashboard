# Architecture

## Implemented locally

```text
FRED observations API
        |
Python CLI -> paginated HTTP client -> validation and normalization
        |                                  |
data/local/raw/fred/UNRATE/<run-id>.json     data/local/processed/UNRATE.json
```

Python 3.11+ is the initial runtime. Standard-library HTTP and JSON keep the ingestion scaffold runnable without dependency installation. `data/indicators.yaml` records catalog metadata; the current implementation intentionally supports only UNRATE and does not dynamically execute catalog entries.

The client requests ascending observations with original units and no frequency transformation. Network requests use a timeout and bounded retry/backoff for HTTP 429, HTTP 5xx, and connection failures. Authentication and other client errors fail immediately. Error output excludes request URLs and API credentials.

Each successful fetch produces a raw archive with all original response pages and a chart-ready latest snapshot. Normalization validates dates, numeric values, realtime fields, duplicate dates, date bounds, and the unemployment rate's 0–100 percent domain. FRED's `.` sentinel becomes JSON `null`. Writes use temporary files and atomic replacement; failed retrieval or validation does not replace the previous snapshot. Raw archival and snapshot publication are separate writes, not a cross-file transaction.

Snapshot contract (shape example only, not real economic data):

```json
{
  "schema_version": 1,
  "series_id": "UNRATE",
  "source": "FRED",
  "source_url": "https://fred.stlouisfed.org/series/UNRATE",
  "title": "Unemployment Rate",
  "units": "Percent",
  "frequency": "Monthly",
  "seasonal_adjustment": "Seasonally Adjusted",
  "retrieved_at": "2026-01-01T00:00:00+00:00",
  "requested_start": "2000-01-01",
  "requested_end": null,
  "observations": [
    {"date": "2000-01-01", "value": null, "realtime_start": "2026-01-01", "realtime_end": "2026-01-01"}
  ]
}
```

Observation dates identify periods, not publication dates. Realtime fields describe the returned FRED data version; preserving them does not implement a full vintage history. Re-runs replace the latest snapshot, accommodating revisions. Concurrent writers are outside the local scaffold's scope.

The Lambda entry point invokes the same ingestion service with local filesystem storage. It defaults to `/tmp/economic-dashboard`, which is ephemeral. It is a handler scaffold only; durable S3/DSQL adapters and deployment packaging remain to be implemented.

## Planned AWS design

```mermaid
flowchart LR
    E[EventBridge schedule] --> I[Python ingestion Lambda]
    F[FRED] --> I
    T[Treasury Fiscal Data] --> I
    I --> S[S3 raw archives]
    I --> D[Aurora DSQL normalized observations]
    D --> A[Python read API Lambda]
    A --> G[HTTP API gateway]
    G --> U[React / TypeScript dashboard]
    W[S3 frontend assets] --> C[CloudFront]
    C --> U
```

API Gateway is a proposed HTTP boundary, additional to the initial stack. Confirm its configuration during the API milestone. Prefer one ingestion path per source and reusable normalization/storage interfaces. A proposed latest-observation key is `(source, series_id, observation_date)`; ingestion runs track retrieval time and raw archive references. Schema, DSQL SQL compatibility, authentication, and transaction behavior must be verified before selecting an upsert strategy.

Frontend: Vite, React, TypeScript, Tailwind with a chart library selected during UI implementation. Read API: series metadata, observations, date filters, and freshness metadata; exact routes remain to be specified. Python analytics will compute explicitly documented transformations rather than mixing series units or frequencies implicitly.

Terraform will define cloud infrastructure. GitHub Actions will run tests and validation, then later use AWS OIDC for authorized deployments. Store FRED credentials server-side in an appropriate AWS secret store; scope IAM access to necessary data and services. Add CloudWatch logging, failed-ingestion alerts, and freshness checks before scheduled operation. Source release dates and retrieval timestamps are separate freshness signals.

No Terraform resources, AWS connections, database migrations, or deployment workflows are created in this foundation.
