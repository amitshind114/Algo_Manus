# Local Experiment Evidence Export

## Scope

Phase 6D exports **read-only local fixture evidence** for one selected persisted experiment batch. The export service reads the existing local experiment store, manifest link, stored KPI summaries and artifact-integrity status. It does not rerun strategy code, recompute a KPI, repair local records, fetch data, submit a paper event or contact any external system.

## Export types

| Export | Always available | Contents |
|---|---|---|
| Evidence summary JSON | Yes, for a persisted batch | Fixture label, batch/research-manifest identity, universe/strategy/revision context, stored KPI summaries, and per-result artifact-integrity status with actual/expected row counts. |
| Detailed evidence JSON | Only when every result is `complete` | Fixture label, batch/manifest identity, exact stored equity points, and completed trade rows for each result. |

Both payloads state that they are fixture-only and not market or broker evidence.

## Verification metadata

Every available export includes a schema identifier, schema version and a deterministic SHA-256 verification value. The hash is calculated from the payload **before** its `verification` field is added, using UTF-8 JSON with sorted keys, compact separators (`","` and `":"`) and ASCII escaping. This canonicalization is recorded in the payload’s verification object.

| Field | Example purpose |
|---|---|
| `schema` | Distinguishes a local evidence-summary payload from a local evidence-detail payload. |
| `schema_version` | Lets offline readers identify the payload shape used to calculate the hash. |
| `verification.algorithm` | Identifies the local content-check algorithm: `sha256`. |
| `verification.sha256` | Lets a user compare two exports generated from identical local persisted evidence. |

The **Reporting & analytics → Local evidence export** panel shows copyable schema/version and SHA-256 values before each available download. Matching values mean the canonical local payload content matched under this implementation. A changed value means the exported content or payload schema/version changed; it does not identify why.

## Refusal rules

Detailed evidence export is refused when any selected result is `unavailable`, `incomplete` or `result_spec_mismatch`. The refusal is all-or-nothing for the selected batch: it does not export a partial detail package, attempt to repair rows, or rebuild omitted detail from a backtest. The summary export remains available so a user can inspect the batch, KPI and integrity evidence that caused the refusal.

## Workbench behavior

Open **Reporting & analytics** and select a persisted batch. The **Local evidence export** section shows a per-result integrity table and a summary download. The detailed-download control appears only for an integrity-complete batch. This local export path is intended for offline inspection of deterministic fixture workflow evidence, not distribution or operational decision-making.

## Limits

The exported files are not a signed audit record, broker statement, market-data lineage certificate, tax record, reconciliation report, backup service, or proof of strategy performance. The service operates only on local SQLite fixture state and cannot determine whether data outside that local store is correct. No broker SDK, provider credential, network data call, scheduler, cloud synchronization, real paper-broker connection or live-execution feature is included.

The SHA-256 field is a local accidental-change/content-comparison aid, **not** a digital signature, tamper-proof ledger, trusted timestamp, identity assertion, key-management system or external verification service. A person who can modify both the local database and the exported file can produce a new matching hash.

This is research and analysis only, not personalized financial advice.
