# Local Evidence Health Detail Inspection

## Scope

Phase 7C adds a read-only detail table beneath the local evidence lifecycle summary. It lists the retained batch and instrument behind each artifact-health observation so a user can inspect local structural context without changing it. The table defaults to non-complete records and can filter to all statuses or one exact status.

## Detail fields

| Field | Meaning |
|---|---|
| Batch ID and instrument ID | Local persisted experiment/result identifiers. |
| Status | Complete, unavailable, incomplete or result-spec-mismatched according to the existing local integrity contract. |
| Result spec / artifact spec | The stored result-spec ID and the local detailed-artifact header spec ID, when a header exists. |
| Trade and equity counts | Actual retained child rows compared with counts declared in the local artifact header. For an unavailable header, expected counts are absent while retained orphan rows, if any, remain visible as actual local rows. |
| Batch created | The timezone-aware local experiment creation timestamp retained with the batch. |

## Limits

The detail view does not identify root cause, confirm broker data, assess market data, validate a strategy, verify performance, reconcile execution, repair a row, regenerate detail, delete a batch, export evidence, alter promotion, or submit an order. It is a local fixture-evidence inspection surface only.

No broker SDK, provider/network call, credential, cloud connection, scheduler, real paper-broker link or live-execution capability is included.

This is research and analysis only, not personalized financial advice.
