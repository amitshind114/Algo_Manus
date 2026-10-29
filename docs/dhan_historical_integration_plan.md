# Dhan Historical-Data Integration Plan

## Objective

Integrate Dhan as a provider-specific historical-market-data source for Algo Manus research and backtesting.

Algo Manus remains a local research, backtesting, and paper-simulation platform. This integration does not add live trading, order execution, account access, positions, holdings, funds, WebSocket execution, scheduling, or Dhan Cloud deployment.

## Delivery phases

### Phase 0 - Preparation

Status: COMPLETE

- Added provider-contract template.
- Added safety-boundary documentation.
- Added boundary and contract-gate tests.
- No network client or provider implementation added.

### Phase 1 - Contract confirmation

Status: COMPLETE

Confirmed from official DhanHQ v2 documentation:

- Base URL: `https://api.dhan.co/v2`
- Daily endpoint: `POST /charts/historical`
- Intraday endpoint: `POST /charts/intraday`
- Authentication header: `access-token`
- Intraday intervals: 1, 5, 15, 25, and 60 minutes
- Intraday availability: up to 5 years, with a 90-day maximum local request chunk
- Timestamps: Unix epoch seconds
- Data API rate limit: 5 requests per second
- Supported segments: `IDX_I`, `NSE_EQ`, `NSE_FNO`, `NSE_CURRENCY`, `BSE_EQ`, `MCX_COMM`, `BSE_CURRENCY`, `BSE_FNO`

### Phase 2 - Research source policy

Status: COMPLETE

Generalized retained-dataset backtesting from Angel One-specific filtering to an explicit `ApprovedResearchSourcePolicy`.

- Default policy remains Angel One-only.
- Unknown providers fail closed.

### Phase 3 - Historical adapter

Status: COMPLETE

Added `DhanHistoricalCandleProvider` behind `MarketDataProviderPort`.

- Added historical-only transport in `dhan_client.py`.
- Added `DhanHistoricalCandleProvider` in `dhan_historical.py`.
- Supports daily candles through `POST /charts/historical`.
- Supports 1m, 5m, 15m, 25m, and 60m candles through `POST /charts/intraday`.
- Splits one explicit retrieval spanning more than 90 days into sequential, non-overlapping 90-day requests.
- Sends documented `instrument` and `oi` fields; currently maps only supported equity segments to `EQUITY` and fails closed for unsupported mappings.
- Converts Dhan epoch-second timestamps to timezone-aware UTC timestamps.
- Rejects malformed, duplicate, out-of-order, empty, OHLC-inconsistent, and negative-volume responses.
- Validates combined chunks for strict chronological ordering and no duplicates, then retains a SHA-256 over concatenated raw chunk responses.
- Uses injectable transport for deterministic network-free tests.
- Contains no order, account, position, holdings, funds, WebSocket, scheduler, or cloud capability.

### Phase 4 - Dataset lineage

Status: COMPLETE

Integrated Dhan historical datasets with the existing immutable SQLite dataset repository and `MarketDataService`.

- Dhan datasets persist with source `dhan`, broker source kind, research use case, retrieval time, source URI, adjustment basis, and raw-response SHA-256.
- Identical retained responses are idempotent and do not duplicate candles.
- A dataset-ID collision with a different raw-content hash now fails closed instead of being silently ignored.
- Different Dhan responses create distinct immutable dataset identities.
- Restart-safe persistence is verified through repository recreation.
- Tests use injected transport and make no network calls.

### Phase 5 - Retained backtesting

Status: COMPLETE

Enabled explicitly approved Dhan datasets to flow through retained-dataset backtesting.

- Added `ApprovedResearchSourcePolicy.for_dhan_research()`.
- Default retained-backtest policy remains Angel One-only.
- Dhan datasets are accepted only when the caller explicitly uses the Dhan research policy.
- End-to-end tests cover Dhan data ingestion, immutable persistence, research validation, retained backtesting, experiment persistence, and manifest lineage.
- Research manifests pin the exact Dhan dataset ID, raw-content SHA-256, information cutoff, and universe snapshot.
- Tests use injected transport and make no network calls.

### Phase 6 - UI retrieval slice

Status: COMPLETE

Added an isolated, reusable Streamlit panel in `ui/dhan_historical.py`.

- Shows display-safe Dhan configuration status.
- Supports manual selection of canonical Dhan instrument ID, interval, and UTC date range.
- Requires an explicit Fetch historical candles button.
- Allows a user-selected intraday range up to the documented five-year availability; the provider performs the 90-day chunking within that one explicit action.
- Never retrieves during Streamlit page render.
- Persists retrieved data through `MarketDataService` and the immutable SQLite dataset repository.
- Displays only safe dataset metadata and named errors.
- Never displays credentials, headers, or raw provider responses.
- Contains no order, account, position, WebSocket, scheduler, fixture-fallback, or cloud capability.
- Is intentionally independent of the current monolithic workbench so it can be mounted after workbench modularization.

## Explicit exclusions

The following are excluded from this integration:

- Dhan order placement, modification, cancellation, super orders, and forever orders.
- Account profile, funds, margins, holdings, positions, trade book, and order book access.
- Live quote endpoints, live market-data polling, and WebSocket subscriptions.
- Dhan Sandbox paper trading treated as virtual-money live-market simulation.
- Scheduled, background, worker, or unattended retrieval.
- Cloud deployment or Dhan Cloud execution.
- Automatic strategy promotion or approval.
- Automatic fallback to fixtures or another provider.
- Silent symbol, expiry, token, or instrument remapping.
- Silent corporate-action adjustment.
