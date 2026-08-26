# Strategy-Family Research Comparison

## Scope

Option J adds one additional **local research-only** strategy alongside the existing SMA crossover reference: `rsi_threshold_reversion` version `1.0.0`. The strategy and comparison tooling use immutable local datasets and retained experiment evidence. They do not create recommendations, rankings, selected strategies, orders, broker sessions, market-price requests, paper fills, or live execution authority.

> A calculated local backtest result is research evidence under declared assumptions. It is not proof of profitability, robustness, future performance, suitability, broker execution quality, or paper/live readiness.

## RSI threshold-reversion strategy

| Aspect | Declared behavior |
| --- | --- |
| Strategy ID / version | `rsi_threshold_reversion` / `1.0.0` |
| Intended scope | Long-only equity research on retained `1d` datasets. |
| Inputs | `rsi_window`, `entry_threshold`, and `exit_threshold`. |
| Parameter validation | The window is an integer from 2 to 250. Thresholds are 0–100 and `entry_threshold` must be strictly lower than `exit_threshold`. |
| Entry signal | RSI crosses from at/above the entry threshold to below it, using only closed supplied bars. |
| Exit signal | RSI crosses from at/below the exit threshold to above it, using only closed supplied bars. |
| Execution model | The common bar backtester can fill a signal only at the **next bar open**, with declared commission and adverse slippage assumptions. |
| Position model | One long position at a time; no shorting, leverage, options execution, intrabar simulation, order-book model, partial fill model, live pricing, or broker action. |

The strategy is deliberately separate from `rsi_mean_reversion`. It makes threshold **crossings** explicit and carries a separate stable strategy ID and parameter revision. Existing SMA crossover behavior remains unchanged.

## Retained family comparison

The Strategy manager can compare two already-retained local research batches. It reports a like-for-like comparison only when both batches share the same universe ID, universe snapshot ID, instrument set, per-instrument dataset IDs, initial cash, quantity, commission, slippage, force-close setting and, where both manifests are present, execution timing.

| Condition | Console behavior |
| --- | --- |
| All declared comparison inputs match | Shows the basis: **same universe, datasets, initial cash, quantity and costs**. |
| Any declared comparison input differs | Shows `not like-for-like` and names the mismatched fields; it does not imply that KPI values are directly comparable. |
| Research manifest and accepted validation resolve for a sample result | Shows **Resolved** immutable research/validation evidence. This is not an approval to paper trade. |
| Research evidence cannot resolve | Shows **Unavailable** and leaves the ordinary paper-promotion/risk gates unchanged. |

The comparison returns retained batch identity, strategy/version, parameter revision, manifest reference, result count, aggregate local net P&L and aggregate local trade count. It deliberately has no score, winner, ranking, recommendation, auto-selection, promotion action or execution path.

## Evidence and limitations

Fixture-workbench records remain deterministic local samples and must not be described as broker data or market performance. Retained broker historical datasets are research evidence only; their validation, source freshness, adjustments, corporate actions, survivorship, execution frictions, liquidity, taxes and regulatory context must be evaluated separately. A comparison controls only the explicit fields above; it does not eliminate selection bias, overfitting, data-snooping, regime dependence, stale metadata, sample insufficiency or operational risk.

The existing paper-promotion resolver continues to require persisted manifest lineage and accepted dataset validation for the chosen batch/result. Independent deterministic paper risk remains required thereafter. No Option J component downloads data, opens a WebSocket, runs on a scheduler, connects to an account, calls a broker, submits/cancels an order or enables live execution.

This is research and analysis only, not personalized financial advice.
