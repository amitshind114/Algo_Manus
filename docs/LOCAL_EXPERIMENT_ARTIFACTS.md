# Local Experiment Artifacts

## Scope

Phase 6B stores detailed output that the existing local fixture backtest has already calculated. Each newly saved result has an artifact record linked to its batch, instrument and immutable result-spec ID. The stored detail is read-only evidence: artifact retrieval never reruns a strategy, changes a metric, fetches data or evaluates a paper order.

## Stored local detail

| Artifact | Stored fields | Ordering | Default bound per result |
|---|---|---|---:|
| Equity curve | Timezone-aware timestamp and equity | Original curve sequence | 5,000 points |
| Completed trade | Entry/exit times, quantity, entry/exit prices, gross P&L and cost | Backtest trade sequence | 5,000 trades |
| Artifact header | Batch, instrument, result-spec ID and expected row counts | One row per saved result | N/A |

The header’s expected counts are checked when artifacts are loaded. A missing header produces an explicit unavailable-artifact result. A header with missing child rows is treated as incomplete persisted data rather than being reconstructed or silently substituted.

## Restart behavior

The workbench reads persisted artifact records from the same local experiment SQLite store used for experiment summaries. **Backtesting** displays the selected result’s stored equity curve and trade table. **Reporting** builds its trade log from stored artifacts for the selected persisted batch. A fixture batch created before Phase 6B has no artifact header, so the UI retains the stored KPI summary and states that detailed local detail is unavailable.

The fixture service now records each batch’s actual local creation time, while dataset-validation evidence remains pinned to its deterministic fixture validation time. This lets the local history select the latest distinct saved run after restart without changing fixture bars, backtest economics or immutable validation evidence.

## Retention and limits

The SQLite repository rejects a result whose detailed artifacts exceed either configured bound before inserting the batch. The defaults are deliberately conservative local limits, not a data-retention policy for a production research warehouse. The implementation does not persist raw market data, indicator values, signals, drawdown curve points, open-position state, external broker events or any account data.

## Limits

All artifacts remain deterministic local fixtures. They are not broker statements, market-data evidence, an execution audit, a valuation service, a tax record, or proof of strategy performance. There is no provider connection, scheduler, cloud sync, real paper-broker connection or live order capability.

This is research and analysis only, not personalized financial advice.
