# Local Build: Current Limitations and Gates

The assembled local build provides tested **contracts and fixtures**, not a claim of production or trading readiness. It supports a local, reproducible path from a validated instrument snapshot to a source-labelled research dataset, parameter revision, bar-based backtest, multi-security result projection, deterministic paper-risk decision and append-only paper event ledger.

| Capability | Current local state | Required before it can be relied on operationally |
|---|---|---|
| Instrument master | Normalized contracts, immutable SQLite snapshots, and a bounded public Angel One adapter with fixture-tested cache rules | A real user-owned download, published-master validation, local sync review, and freshness/data-quality checks |
| Research data | Source lineage/policy contracts and fixture persistence | Licensed/approved data terms, actual historical fetch, corporate-action basis, session/calendar handling and quality controls |
| Backtesting | Deterministic long-only next-bar fill model with explicit costs/slippage | Walk-forward evaluation, point-in-time data controls, broader strategy coverage, Indian charges/taxes and deeper execution assumptions |
| Leaderboard | Comparable KPI rows from one parameter revision under identical stated assumptions | User-selected broker-synced universe, warning thresholds, data completeness rules and research-review workflow |
| Paper trading | Local simulated order state, risk decision and event ledger | Broker-authoritative marks, portfolio projection/reconciliation, session state, fills/partial fills and longer paper observation |
| Local UI | Streamlit shell with disabled controls until valid data/read models exist | Application-service read/write wiring after the above inputs are implemented and reviewed |
| Cloud/live | Not implemented | Separate paper-pilot review, security/compliance assessment, deployment design, broker approval and explicit live-readiness decision |

Bounded public instrument, manual session, and research-only historical-candle adapters exist for explicit caller-invoked local workflows. No broker account/profile/funds/holdings/positions state, live quotes, WebSocket feed, order endpoint, external scheduler, cloud service, or live order is present in the current codebase. Local credentials and short-lived session values remain process-local and are never rendered, logged, or persisted. The next technical work must remain behind these constraints until separately approved.

This is research and analysis only, not personalized financial advice.
