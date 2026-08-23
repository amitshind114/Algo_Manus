# Local Experiment Artifact Integrity

## Scope

Phase 6C adds a **read-only integrity status** for each stored fixture experiment result. It compares the persisted experiment result, artifact header and ordered child rows without rerunning a backtest, recalculating a metric, altering local SQLite records or accessing a provider.

## Status rules

| Status | Read-only rule | Workbench behavior |
|---|---|---|
| `complete` | The artifact header result-spec ID matches the saved result specification, and expected trade/equity counts match stored child-row counts. | Backtesting and Reporting may display the stored detail. |
| `unavailable` | The saved result has no artifact header, including batches created before Phase 6B. | KPI summary remains visible; detailed artifact display is withheld. |
| `incomplete` | The artifact header exists, but its expected trade or equity count differs from the actual stored row count. | KPI summary remains visible; detailed artifact display is withheld. |
| `result_spec_mismatch` | The artifact header identifies a different result specification than the persisted experiment result. | KPI summary remains visible; detailed artifact display is withheld. |

The **Multi-test leaderboard → Experiment history** section presents these statuses per batch and instrument. Its filter only narrows the local history table; it does not delete records, repair artifacts, create data or alter research-to-paper evidence.

## Evidence fields

Each integrity row exposes the local batch and instrument identity, status, actual/expected completed-trade count, actual/expected equity-point count, and result-spec match. Counts are metadata integrity checks, not an assessment of strategy quality, profitability, broker execution or market-data quality.

## Limits

This is a local fixture-store consistency feature, not a cryptographic audit, database-recovery procedure, broker reconciliation, market-data validation, backup service or compliance record. It cannot detect every form of database corruption, and it does not modify a non-complete artifact. Repair, migration and retention policy remain separately scoped future work.

All displayed inputs remain deterministic local fixtures. No broker SDK, provider connection, credential, account record, scheduler, cloud process, real paper-broker connection or live-execution capability is included.

This is research and analysis only, not personalized financial advice.
