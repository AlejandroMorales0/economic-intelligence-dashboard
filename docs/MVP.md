# MVP

## Purpose and audience

Build a reproducible portfolio project that helps users inspect national U.S. economic conditions and demonstrates data engineering, analytics, frontend development, and infrastructure practices. Data must retain source attribution, units, frequency, and retrieval timestamps.

## Scope

| Domain | Initial candidate | Source | Status |
| --- | --- | --- | --- |
| Labor | Unemployment rate (`UNRATE`) | FRED / BLS | Local ingestion, read API, and chart implemented |
| Growth | Real GDP (`GDPC1`) | FRED / BEA | Planned |
| Inflation | CPI index (`CPIAUCSL`) and derived YoY inflation | FRED / BLS | Local ingestion, analytics, read API, and chart implemented |
| Interest rates | Effective federal funds rate (`FEDFUNDS`) | FRED / Federal Reserve | Planned |
| Fiscal health | Federal debt and budget balance | Treasury Fiscal Data | Endpoint and definitions to select |

Remaining candidate indicators require metadata verification before implementation. CPI level is not itself an inflation rate; year-over-year inflation is an explicitly labeled derived metric. Fiscal ratios need aligned units and time periods.

## First vertical slice

1. Retrieve `UNRATE` from FRED with a server-side API key.
2. Save raw responses with source and retrieval provenance.
3. Normalize observations into date/value records, retaining FRED realtime fields and nulls for missing values.
4. Expose the stored series through a local read API (implemented).
5. Render a React unemployment-rate line chart with date filters, percent units, source attribution, latest available observation in the selected range, and retrieval timestamp (implemented).

Local ingestion acceptance criteria:

- CLI accepts an inclusive date range and fails clearly on missing credentials or malformed input.
- Client supports pagination, timeouts, and bounded retries for rate limits and transient failures; errors do not reveal credentials.
- Observations are unique by date, ordered, numeric or null, and within the requested interval.
- Raw data is retained and refreshes atomically replace the latest processed snapshot.
- Offline tests cover retrieval, normalization, failures, and repeat ingestion.

Full vertical-slice acceptance criteria:

- API serves persisted data without requesting FRED on every page load.
- Chart handles loading, empty, missing-value, and error states and does not interpolate missing observations as zero.
- UI distinguishes observation period from data retrieval time.
- End-to-end checks verify the fetched series reaches the chart.

The read API and frontend implement these behaviors locally. Backend tests exercise ingestion-to-API delivery and date filtering; frontend tests exercise contract validation, loading, errors/retry, missing values, empty ranges, and consistent filtering. Browser review verifies actual chart rendering and representative range controls. AWS operation, production API hosting, and scheduled refresh remain later milestones.

## Second vertical slice: inflation

Implemented locally:

- Retrieve original-unit CPIAUCSL with a 12-month lookback before the requested chart period.
- Archive raw responses and atomically publish a normalized index snapshot, preserving source and retrieval provenance.
- Derive `CPIAUCSL_YOY` by matching the same calendar month one year earlier; calculate before filtering.
- Serve both original CPI and derived inflation through the reusable read API.
- Add Labor/Inflation navigation with independent date ranges, source attribution, methodology, latest-in-range rate, and observation table.
- Support negative inflation and preserve nulls when current/prior values or months are missing.

The dashboard explicitly labels the seasonally adjusted CPI input; this differs from using the unadjusted CPI for the commonly reported headline rate. Tests cover known calculations, lookback, missing months, deflation, failures, API filtering, and domain switching. Local runtime verification uses actual fetched CPI data.

## Later milestones

Add the other domains, document transformations, build freshness monitoring, and validate cross-series comparisons. Then introduce scheduled AWS ingestion, durable S3 storage, Aurora DSQL persistence, Terraform, and GitHub Actions validation/deployment workflows. Deployment requires a separate implementation phase.

## Outside the MVP

State/county data, forecasts, causal claims, trading recommendations, user accounts, and comprehensive vintage analysis. No AWS deployment is part of the current local foundation.
