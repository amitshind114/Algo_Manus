# Local Corporate-Action and Calendar Review Evidence Gate

## Purpose and evidence boundary

Option M adds a **local declaration and evidence-retention gate** for two review categories associated with one retained research-use candle dataset: corporate actions and calendar events. It makes the declared review scope, source-reference text, review time, policy, and blockers visible and durable. It does not retrieve, parse, validate, or reconcile any external corporate-action or calendar source.

> `REVIEW_COMPLETE` is a local statement about the shape and recency of two manually declared review records. It is **not** evidence that actions or events were complete, correctly identified, applicable to the instrument, represented in the candles, or reflected by the adjustment basis.

| Category | Local gate records | Local gate never does |
|---|---|---|
| Corporate-action review | A declared disposition, candle-time scope, local source reference, note, and review time | Download splits/dividends/rights/merger data, infer an adjustment, alter OHLCV, or verify the reference |
| Calendar review | A declared disposition, candle-time scope, local source reference, note, and review time | Download earnings/exchange/holiday/other events, infer a signal cutoff, or verify the reference |
| Dataset lineage | Dataset/instrument/interval IDs, immutable provenance content hash, and retained adjustment-basis text | Replace a dataset, amend provenance, or certify the dataset as complete |
| Downstream workflow | Nothing | Change validation, research promotion, robustness, paper-run evidence, risk control, paper events, orders, or execution |

## Declared local policy and assessment states

The `LocalDatasetReviewPolicy` contains a version and a positive maximum review age. The assessment time is timezone-aware and retained. A declaration must have a timezone-aware inclusive scope, nonblank local source reference, nonblank note, and a disposition. The service assesses the complete first-to-last candle window of the selected retained dataset.

| State | Meaning |
|---|---|
| `REVIEW_COMPLETE` | Both manual declarations are marked `REVIEWED`, cover the full retained candle window, have review times no later than assessment, and are within the local age policy. It remains informational only. |
| `BLOCKED` | At least one declaration is absent, unresolved, scope-incomplete, future-dated relative to assessment, or stale. All observed reasons are retained. |

The gate does not calculate adjusted prices or decide whether any particular event should affect a strategy, backtest, or paper simulation. A review statement therefore cannot cure an invalid dataset, waive an existing validation warning, override a kill switch, or substitute for research promotion or proposal-level risk evaluation.

## Named blockers

| Blocker | Condition |
|---|---|
| `CORPORATE_ACTION_REVIEW_MISSING` | No corporate-action declaration was supplied. |
| `CALENDAR_REVIEW_MISSING` | No calendar declaration was supplied. |
| `CORPORATE_ACTION_REVIEW_UNRESOLVED` | The corporate-action declaration was explicitly retained as unresolved. |
| `CALENDAR_REVIEW_UNRESOLVED` | The calendar declaration was explicitly retained as unresolved. |
| `CORPORATE_ACTION_REVIEW_SCOPE_INCOMPLETE` | The declared corporate-action scope does not cover the full retained candle window. |
| `CALENDAR_REVIEW_SCOPE_INCOMPLETE` | The declared calendar scope does not cover the full retained candle window. |
| `CORPORATE_ACTION_REVIEW_TIME_AFTER_ASSESSMENT` | The declared corporate-action review time is later than the assessment time. |
| `CALENDAR_REVIEW_TIME_AFTER_ASSESSMENT` | The declared calendar review time is later than the assessment time. |
| `CORPORATE_ACTION_REVIEW_STALE` | The corporate-action declaration is older than the policy maximum at assessment. |
| `CALENDAR_REVIEW_STALE` | The calendar declaration is older than the policy maximum at assessment. |

## Local retention and workbench behavior

Evidence is retained immutably in `dataset_review.sqlite3` under `ALGO_MANUS_DATA_DIR` (default `~/.algo-manus`). Its deterministic ID includes the immutable dataset/provenance lineage, both declaration payloads, policy version and age limit, retained blocker list, and exact assessment time. Repeating the same assessment resolves the existing evidence record; a conflicting payload under the same ID fails explicitly.

The **Data & instruments** page offers a **Record local review evidence** control. For a fixture dataset, an empty reference remains an explicit missing-review blocker. Supplying a `local://` or other text reference creates only a manually declared record; the workbench never opens, validates, downloads, synchronizes, or interprets that reference. The visible table labels both `BLOCKED` and `REVIEW COMPLETE` states and repeats that complete is not authorization or verification.

## Data and market limitations

The adjustment-basis text in a retained dataset provenance record describes the dataset provider’s stated basis; Option M does not independently confirm split, dividend, rights, bonus, consolidation, merger, delisting, symbol-change, holiday, earnings, exchange-session, or other calendar treatment. Data may still be stale, incomplete, misadjusted, subject to survivorship bias, affected by evolving instrument identity, or unsuitable for a given research question.

Fixture declarations are workflow examples, not corporate-action data, calendar data, broker data, market evidence, performance evidence, or recommendations. A manually entered reference is not a data source connection and must not be treated as an external data retrieval capability.

Option M adds no broker account/profile/funds/RMS/holdings/positions capability, LTP/live-price feed, WebSocket, corporate-action or calendar downloader, scheduler, worker, external queue, cloud service, order/cancellation route, paper broker, autonomous execution, or recommendation feature.

This is research and analysis only, not personalized financial advice.
