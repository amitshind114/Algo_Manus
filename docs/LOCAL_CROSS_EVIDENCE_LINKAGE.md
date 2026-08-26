# Read-Only Cross-Evidence Linkage

## Purpose and strict boundary

Option N provides a **read-only local view** from one retained Option L paper-run eligibility evidence record to retained Option M dataset-review evidence. The view explains whether one dataset-review record shares the paper evidence’s exact retained dataset and instrument identifiers. It does not create, update, delete, select, rank, approve, promote, or invalidate any evidence record.

> A linkage result is an identity relationship only. It does not make a paper-run row complete, a manual review declaration correct, a dataset valid, a strategy suitable, a paper proposal risk-cleared, or an action executable.

| Retained source | Fields used by the linkage view | Fields intentionally not used |
|---|---|---|
| Paper-run evidence | Evidence ID, batch ID, state, dataset ID, and instrument ID | P&L, returns, ranking, strategy selection, promotion outcome, order, or risk decision |
| Dataset-review evidence | Evidence ID, state, dataset ID, instrument ID, and named review blockers | Reference contents, inferred actions/events, adjustment calculation, or source verification |

## Linkage states

| State | Meaning |
|---|---|
| `LINKED_REVIEW_COMPLETE` | One retained manual dataset-review record shares exact dataset and instrument identifiers and has `REVIEW_COMPLETE`. This is still informational only. |
| `LINKED_REVIEW_BLOCKED` | One retained manual dataset-review record shares exact identifiers but itself has `BLOCKED` state. Its recorded blockers are carried as `DATASET_REVIEW_BLOCKED:<reason>`. |
| `REVIEW_EVIDENCE_MISSING` | No retained dataset-review record is available for the retained paper evidence’s exact dataset and instrument relationship, or the paper record lacks dataset lineage. |
| `LINEAGE_MISMATCH` | Review records exist for only the same instrument and a different dataset, only the same dataset and a different instrument, or both. The view reports the observed mismatch conditions without substituting a “similar” record. |
| `PAPER_EVIDENCE_MISSING` | The requested paper-run evidence ID is not retained. |

The read model checks up to the bounded 64 most-recent review records. It preserves repository ordering and does not use performance results or any “best” record selection. When an exact record is unavailable, it explicitly reports missing or mismatch conditions; it never maps by symbol, display name, source reference, strategy, date similarity, or market interpretation.

## Workbench behavior

The **Data & instruments** page renders the **Read-only paper-run and dataset-review linkage** section after retained dataset-review rows. It offers only a selector for an already-retained paper-run evidence ID and shows the relationship state, paper/review IDs, retained dataset/instrument fields, paper evidence state, review evidence state, and named conditions.

The selector cannot create a paper-run assessment or a review declaration. It cannot change paper-run evidence, review evidence, research promotion, robustness evidence, central risk controls, the kill switch, the paper ledger, an order, a broker session, or a dataset. When no paper-run evidence exists, the page reports that absence and provides no action to create one.

## Important limitations

`LINKED_REVIEW_COMPLETE` requires exact retained identifiers, not a data-quality conclusion. The linked Option M review record remains a manual local declaration: its source references are not opened, fetched, verified, or interpreted. Therefore the linkage does not establish corporate-action correctness, calendar completeness, adjustment treatment, event applicability, historical data completeness, absence of survivorship bias, or future market behavior.

Fixture relationships are workflow examples only. They are not broker data, corporate-action data, calendar data, market evidence, a performance record, an execution record, or a recommendation. The feature adds no live price/feed, WebSocket, corporate-action/calendar downloader, broker account/profile/funds/RMS/holdings/positions capability, broker order/cancel endpoint, paper broker, scheduler, worker, external queue, cloud service, or autonomous execution.

This is research and analysis only, not personalized financial advice.
