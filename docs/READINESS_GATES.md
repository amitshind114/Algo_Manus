# Readiness Gates

The local build intentionally stops before broker-authoritative paper operation, cloud operation, and live execution. Bounded caller-invoked public-master, manual session, and research-only historical-candle adapters exist, but each data workflow remains explicitly gated and local-first. Each next step requires a distinct approval; passing an earlier gate does not approve the next one.

| Gate | What it enables | Evidence required before enabling | Current state |
|---|---|---|---|
| Broker instrument/data sync | A user-owned, opt-in provider adapter may download the official public instrument master and approved research data to the local cache | Provider terms/permissions, adapter tests against a user-owned account, source/refresh validation, error/retry behavior and local secret handling | Bounded public-master, manual session, and research-candle adapters exist; no user-owned dataset is currently verified in the local build |
| Local paper observation | Longer local paper runs with approved broker-authoritative marks and validated selected universe | Data freshness rules, session/calendar checks, portfolio projection/reconciliation, paper incident log and review of risk thresholds | Not implemented; current paper lifecycle uses local fixtures only |
| Cloud paper environment | Remote research/paper services, monitoring and persistence without real-order capability | Deployment design, authentication, secret storage, backup/recovery, access controls, resource/cost decision and operational runbook | Not implemented or selected |
| Controlled live pilot | A narrowly scoped real broker execution boundary | Broker/exchange/compliance review, independent risk/security testing, reconciled account/position state, kill/recovery evidence, human approvals and written pilot limits | Explicitly excluded |

The project must never enable a later gate merely because a dashboard appears functional, a provider adapter is present, or a historical backtest produces a positive result. No adapter presence is evidence of provider permission, data quality, broker-authoritative paper readiness, or live readiness.

This is research and analysis only, not personalized financial advice.
