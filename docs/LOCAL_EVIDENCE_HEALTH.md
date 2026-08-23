# Local Evidence Health Summary

## Scope

Phase 7B aggregates the existing local detailed-artifact integrity checks across every retained experiment result. The Overview lifecycle panel reports how many local results are complete, unavailable, incomplete or result-spec-mismatched. It reads the existing experiment, artifact header, trade-row and equity-row records without changing any of them.

## Status meanings

| Status | Local observation | Phase 7B response |
|---|---|---|
| Complete | A local artifact header exists, its result-spec ID matches, and its stored row counts equal actual detail rows. | Count it as integrity-complete only. |
| Unavailable | A stored experiment result has no local detailed-artifact header. | Count it; do not recreate detail. |
| Incomplete | A header exists but local completed-trade or equity-point row counts differ from its declared counts. | Count it; do not repair rows. |
| Result-spec mismatch | A header exists but its result-spec ID does not match the retained experiment result. | Count it; do not replace either record. |

## Limits

The summary is a local structural coverage view, not a data-quality audit, market-data validation, broker reconciliation, performance assessment, backup test, execution check or recommendation. It cannot identify the source of a mismatch and it intentionally has no authority to regenerate, repair, delete, export, promote, submit, schedule, synchronize or back up anything.

All values refer to deterministic local fixtures only. No broker SDK, provider/network call, credential, cloud connection, real paper-broker link or live-execution capability is included.

This is research and analysis only, not personalized financial advice.
