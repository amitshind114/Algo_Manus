# Dhan Historical-Data Integration Plan

## Objective

Integrate Dhan as a provider-specific historical-market-data source for Algo Manus research and backtesting.

Algo Manus remains a local research, backtesting, and paper-simulation platform. This integration does not add live trading, order execution, account access, positions, holdings, funds, WebSocket execution, scheduling, or Dhan Cloud deployment.

## Delivery phases

### Phase 0 - Preparation

- Add provider-contract template.
- Add safety-boundary documentation.
- Add failing boundary and contract-gate tests.
- Add no network client and no provider implementation.

### Phase 1 - Contract confirmation

- Confirm every required Dhan historical-data contract field from official documentation.
- Record confirmed values in `docs/dhan_provider_contract.md`.
- Block implementation until the contract is complete.

### Phase 2 - Research source policy

- Generalize retained-dataset backtesting from Angel One-specific filtering to an explicit approved-source policy.
- Fail closed for unknown providers.
- Preserve existing Angel One behavior through explicit policy configuration.

### Phase 3 - Historical adapter

- Add a Dhan historical-data-only transport client.
- Implement `DhanHistoricalCandleProvider` behind `MarketDataProviderPort`.
- Normalize Dhan responses into immutable `Candle` values.
- Use injectable transport in tests.
- Do not implement order, account, position, WebSocket, scheduler, or cloud behavior.

### Phase 4 - Dataset lineage

- Persist normalized Dhan candles through the existing immutable dataset repository.
- Retain raw-response SHA-256 provenance.
- Link instrument snapshot, validation policy, retrieval time, and dataset identity.
- Reject silent overwrites, silent merges, and inconsistent duplicate responses.

### Phase 5 - Retained backtesting

- Allow explicitly approved Dhan datasets to flow through retained-dataset backtesting.
- Pin dataset ID, raw-content hash, instrument snapshot, strategy version, parameters, and policy versions in the backtest manifest.

### Phase 6 - UI retrieval slice

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
