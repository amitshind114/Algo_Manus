# Local Experiment Evidence Export

## Scope

Phase 6D exports **read-only local fixture evidence** for one selected persisted experiment batch. The export service reads the existing local experiment store, manifest link, stored KPI summaries and artifact-integrity status. It does not rerun strategy code, recompute a KPI, repair local records, fetch data, submit a paper event or contact any external system.

## Export types

| Export | Always available | Contents |
|---|---|---|
| Evidence summary JSON | Yes, for a persisted batch | Fixture label, batch/research-manifest identity, universe/strategy/revision context, stored KPI summaries, and per-result artifact-integrity status with actual/expected row counts. |
| Detailed evidence JSON | Only when every result is `complete` | Fixture label, batch/manifest identity, exact stored equity points, and completed trade rows for each result. |

Both payloads state that they are fixture-only and not market or broker evidence.

## Refusal rules

Detailed evidence export is refused when any selected result is `unavailable`, `incomplete` or `result_spec_mismatch`. The refusal is all-or-nothing for the selected batch: it does not export a partial detail package, attempt to repair rows, or rebuild omitted detail from a backtest. The summary export remains available so a user can inspect the batch, KPI and integrity evidence that caused the refusal.

## Workbench behavior

Open **Reporting & analytics** and select a persisted batch. The **Local evidence export** section shows a per-result integrity table and a summary download. The detailed-download control appears only for an integrity-complete batch. This local export path is intended for offline inspection of deterministic fixture workflow evidence, not distribution or operational decision-making.

## Limits

The exported files are not a signed audit record, broker statement, market-data lineage certificate, tax record, reconciliation report, backup service, or proof of strategy performance. The service operates only on local SQLite fixture state and cannot determine whether data outside that local store is correct. No broker SDK, provider credential, network data call, scheduler, cloud synchronization, real paper-broker connection or live-execution feature is included.

This is research and analysis only, not personalized financial advice.
