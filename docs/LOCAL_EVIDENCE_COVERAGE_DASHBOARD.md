# Read-Only Evidence Freshness and Lineage-Coverage Dashboard

## Purpose and hard boundary

Option O adds a **bounded, read-only local dashboard** over retained Option K robustness evidence, Option L paper-run evidence, Option M dataset-review evidence, and Option N exact-link relationships. It reads at most the 64 most-recent records from each local evidence repository, aggregates display-time counts, and renders one coverage row per retained paper-run evidence record.

> The dashboard is an observation surface, not a new approval mechanism. It never retrieves market or corporate-action data, writes evidence, updates a review declaration, reruns a backtest, selects a strategy, changes promotion or risk state, creates a paper event, or initiates any external action.

## Declared display policy

The fixture workbench uses `local-evidence-coverage-v1` with a **90-day display-time age limit**. The service evaluates ages at the moment its local read occurs. A freshness result is not an assertion about source quality, data validity, market relevance, suitability, future performance, or operational readiness.

| Freshness | Meaning |
|---|---|
| `CURRENT` | The retained record’s creation or assessment time is not later than the display read and is within the declared 90-day age limit. |
| `STALE` | The retained record is older than the declared display age limit. |
| `UNKNOWN` | A referenced record is absent, or its recorded timestamp is after the display read. The dashboard does not repair, infer, or replace it. |

## Summary-count semantics

| Dashboard count | What it counts | What it does **not** mean |
|---|---|---|
| Paper / robustness / review total, current, stale | Independently retained records read from the relevant local store | Dataset validation, source quality, strategy validity, paper authorization, or execution readiness |
| Paper / review blocked | Retained records whose own immutable state is `BLOCKED` | A new decision, changed gate, or permission to remediate automatically |
| Robustness missing | Paper-run rows whose recorded robustness evidence ID is absent from the bounded local store | That another robustness result may be substituted |
| Review missing | Paper-run rows with `REVIEW_EVIDENCE_MISSING` from the exact Option N relation | A claim that no corporate-action or calendar event exists |
| Exact review links | Paper-run rows with exact dataset and instrument identity plus `LINKED_REVIEW_COMPLETE` | A verified review reference, adjustment conclusion, data-quality certification, risk clearance, or paper approval |
| Exact link blocked / lineage mismatch | Paper-run rows linked to a blocked review record or finding only a dataset/instrument mismatch | An automatic fix, source lookup, remapping, or fallback relationship |

Coverage rows retain the selected paper evidence ID, batch, dataset and instrument identity, paper state and freshness, referenced robustness ID/freshness, linked review ID/freshness, Option N relationship state, and all display-time conditions. Conditions may therefore show both an independently retained block reason and a separate freshness or lineage condition.

## Workbench behavior

The **Overview** page shows no control for refreshing, recording, changing, or resolving evidence. When no paper-run evidence is retained, it displays an explicit empty state rather than constructing a row. When evidence is retained, it displays the counts and one row per paper-run evidence record. An exact link remains visible even if the paper-run row is independently blocked; the two facts are deliberately not conflated.

The dashboard is local-only. It does not call a broker, price feed, WebSocket, calendar service, corporate-action service, cloud resource, queue, timed background process, order endpoint, cancellation endpoint, paper broker, or execution path.

## Limitations

The displayed fixture records are deterministic local sample evidence, not broker data, live market evidence, event data, portfolio data, performance proof, or a recommendation. Dataset-review evidence remains only a manual declaration: a supplied reference is not opened, downloaded, checked, interpreted, or applied to candles. Current/stale/unknown status is derived solely from retained timestamps under the declared local display policy and does not establish data completeness, corporate-action correctness, calendar coverage, survivorship-bias absence, or suitability.

This is research and analysis only, not personalized financial advice.
