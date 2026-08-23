# Local Evidence Health Scope Filters

## Scope

Phase 7E adds a shared, read-only display scope to the local evidence lifecycle panel. A user can select one retained batch or all retained batches and can select an inclusive local batch-creation date range. The resulting scope is applied consistently to the current health totals, filtered detail table, and chronological history table.

## Semantics

| Control | Behavior |
|---|---|
| Lifecycle batch scope | Selects all retained batches or one exact retained batch ID. An unknown batch ID is invalid in the application service. |
| Inclusive batch creation dates | Includes local batches whose stored timezone-aware creation timestamps fall on or between the selected calendar days, inclusive. The workbench expands the start to `00:00:00` UTC and the end to `23:59:59.999999` UTC. |
| Combined scope | Both filters apply together. A valid retained batch can produce an empty display if its creation time lies outside the selected range. |

The service rejects a scope start later than its end and requires timezone-aware bounds. It performs no write, repair, recreation, deletion, export, sync, provider lookup, promotion change or execution action.

## Limits

Scope filtering only changes the currently displayed retained local fixture evidence. It does not establish data quality, market coverage, broker state, strategy validity, performance, lifecycle causality, backup readiness or investment suitability.

No broker SDK, provider/network call, credential, cloud connection, scheduler, real paper-broker link or live-execution capability is included.

This is research and analysis only, not personalized financial advice.
