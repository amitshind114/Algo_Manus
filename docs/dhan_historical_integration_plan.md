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
- Intraday maximum window: 90 days
- Timestamps: Unix epoch seconds
- Data API rate limit: 5 requests per second
- Supported segments: `IDX_I`, `NSE_EQ`, `NSE_FNO`, `NSE_CURRENCY`, `BSE_EQ`, `MCX_COMM`, `BSE_CURRENCY`, `BSE_FNO`

Implementation constraints:

- The adapter must fail closed if the provider contract, instrument mapping, credentials, interval, or request window is invalid.
- Intraday requests must not exceed 90 days.
- Epoch-second timestamps must be converted to timezone-aware UTC timestamps.
- Responses must be validated for ordering, duplicates, OHLC consistency, and volume validity.
- Data must be treated as unadjusted/unknown unless Dhan explicitly confirms an adjustment basis.

### Phase 2 - Research source policy

Status: PENDING

- Generalize retained-dataset backtesting from Angel One-specific filtering to an explicit approved-source policy.
- Fail closed for unknown providers.
- Preserve existing Angel One behavior through explicit policy configuration.

### Phase 3 - Historical adapter

Status: PENDING

- Add a Dhan historical-data-only transport client.
- Implement `DhanHistoricalCandleProvider` behind `MarketDataProviderPort`.
- Normalize Dhan responses into immutable `Candle` values.
- Use injectable transport in tests.
- Do not implement order, account, position, WebSocket, scheduler, or cloud behavior.

### Phase 4 - Dataset lineage

Status: PENDING

- Persist normalized Dhan candles through the existing immutable dataset repository.
- Retain raw-response SHA-256 provenance.
- Link instrument snapshot, validation policy, retrieval time, and dataset identity.
- Reject silent overwrites, silent merges, and inconsistent duplicate responses.

### Phase 5 - Retained backtesting

Status: PENDING

- Allow explicitly approved Dhan datasets to flow through retained-dataset backtesting.
- Pin dataset ID, raw-content hash, instrument snapshot, strategy version, parameters, and policy versions in the backtest manifest.

### Phase 6 - UI retrieval slice

Status: PENDING

- Add a manual Dhan historical-retrieval panel after workbench modularization.
- Never retrieve during page render.
- Show display-safe configuration and error states only.
- Do not display credentials or raw responses.

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
