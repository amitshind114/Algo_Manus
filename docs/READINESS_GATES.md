# Readiness Gates

The local build intentionally stops before broker access, cloud operation and live execution. Each next step requires a distinct approval; passing an earlier gate does not approve the next one.

| Gate | What it enables | Evidence required before enabling | Current state |
|---|---|---|---|
| Broker instrument/data sync | A user-owned, opt-in provider adapter may download the official instrument master and approved research data to the local cache | Provider terms/permissions, adapter tests against a user-owned account, source/refresh validation, error/retry behavior and local secret handling | Not implemented; no credentials or network code in the repository |
| Local paper observation | Longer local paper runs with approved broker-authoritative marks and validated selected universe | Data freshness rules, session/calendar checks, portfolio projection/reconciliation, paper incident log and review of risk thresholds | Not implemented; current paper lifecycle uses local fixtures only |
| Cloud paper environment | Remote research/paper services, monitoring and persistence without real-order capability | Deployment design, authentication, secret storage, backup/recovery, access controls, resource/cost decision and operational runbook | Not implemented or selected |
| Controlled live pilot | A narrowly scoped real broker execution boundary | Broker/exchange/compliance review, independent risk/security testing, reconciled account/position state, kill/recovery evidence, human approvals and written pilot limits | Explicitly excluded |

The project must never enable a later gate merely because a dashboard appears functional or a historical backtest produces a positive result.

This is research and analysis only, not personalized financial advice.
