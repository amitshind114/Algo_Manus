# Dhan Safety Boundary

## Permanent boundary

Algo Manus may use Dhan only as a historical-market-data source for local research, dataset validation, backtesting, and local paper simulation.

Algo Manus must not contain an executable path to Dhan order placement, modification, cancellation, account access, funds, margins, holdings, positions, trade book, order book, live order management, WebSocket execution, scheduling, or Dhan Cloud deployment.

## Allowed capabilities

- Historical candle retrieval.
- Response normalization into immutable local candles.
- Raw-response provenance and hashing.
- Local immutable dataset retention.
- Research dataset validation and review.
- Retained-dataset backtesting.
- Local paper simulation using explicitly approved data.

## Forbidden capabilities

- Dhan order placement.
- Dhan order modification.
- Dhan order cancellation.
- Dhan super orders or forever orders.
- Account profile access.
- Funds or margin access.
- Holdings access.
- Positions access.
- Trade book access.
- Order book access.
- Live WebSocket order execution.
- Background or scheduled retrieval.
- Dhan Cloud deployment.
- Automatic strategy promotion.

## Credential rule

Dhan credentials must be supplied through local environment configuration only.

Credentials must not be committed, logged, displayed, embedded in fixtures, persisted in SQLite evidence, or included in error messages.

If a Dhan credential can also place orders, the preferred future architecture is a separate local data gateway that holds the credential and exposes only normalized historical data to Algo Manus.

## Future live execution

Any future Dhan Cloud execution runner must be a separately approved and separately isolated system.

It must have separate credentials, runtime, database, logs, risk controls, reconciliation, monitoring, and rollback procedures. It must not share the Algo Manus research repository or its execution boundary.
