# Local Evidence Lifecycle Visibility

## Scope

Phase 7A adds a read-only snapshot of the local experiment-evidence store. The snapshot reports whether the workbench is using persistent local SQLite or an in-memory fixture store, local file size, retained batch/result/artifact/trade/equity counts, oldest/newest batch timestamps, and configured per-result artifact bounds.

The workbench presents this information in **Overview → Local evidence lifecycle**. Reading the snapshot does not run a strategy, validate market data, touch broker state, repair an artifact, compact a database, delete history, create a backup or synchronize any file.

## Fields

| Field | Meaning | Does not mean |
|---|---|---|
| Database size | Current byte size of the local SQLite experiment file. | Backup size, safe capacity, integrity proof or cloud-storage usage. |
| Stored batches/results/artifact headers | Counts of retained local experiment and detailed-artifact records. | Quality, profitability, broker confirmation or audit completeness. |
| Completed local trades/equity points | Counts of stored fixture detail rows. | Real trades, executions, market observations or account activity. |
| Oldest/newest batch | Earliest/latest retained local batch creation timestamps. | Market-data coverage, retention guarantee or trusted timestamp. |
| Artifact bounds | Current configured per-result limits accepted at local persistence time. | A cleanup policy, database quota or automatic deletion threshold. |

## Limits

Lifecycle visibility is not lifecycle management. This phase adds **no** cleanup, deletion, compaction, archive, backup, restore, export-to-cloud, retention automation or recovery action. The local store may still require manual filesystem and operating-system care outside the application. No broker SDK, provider, credential, scheduler, cloud connection, real paper-broker link or live-execution capability is involved.

All counts refer to deterministic local fixtures only and are not trading evidence or personalized financial guidance.

This is research and analysis only, not personalized financial advice.
