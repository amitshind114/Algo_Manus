# Backtest Metrics and Research Artifacts

## Scope

Phase 2D extends the local, deterministic bar backtester’s result contract. It does not add real data, portfolio cash allocation, partial fills, spread modelling, a broker adapter or a performance claim. All values remain dependent on the run’s immutable specification, data evidence and execution assumptions.

## Existing metrics retained unchanged

| Metric | Definition |
|---|---|
| Net P&L | Final simulated cash minus starting cash. |
| Total return % | Net P&L divided by starting cash, multiplied by 100. |
| Maximum drawdown % | Largest peak-to-equity decline in the equity curve. |
| Trade count | Number of completed trade records. |
| Win rate % | Positive-net-P&L trades divided by completed trades, multiplied by 100. |
| Profit factor | Sum of positive trade net P&L divided by absolute sum of negative trade net P&L; unavailable when no loss exists. |

## Added metrics

| Metric | Definition | Availability rule |
|---|---|---|
| CAGR % | Annualized growth from initial to final equity using elapsed curve time and a 365.25-day year. | Unavailable unless final equity is positive and the curve spans at least 365 days. |
| Sharpe ratio | Mean equity-period return divided by population standard deviation of returns, annualized by `sqrt(252)` for a `1d` dataset; risk-free rate is currently 0. | Unavailable for fewer than two returns, zero variance or an interval without a declared annualization basis. |
| Sortino ratio | Mean equity-period return divided by root-mean-square downside return, annualized by `sqrt(252)` for a `1d` dataset; target return is currently 0. | Unavailable for fewer than two returns, zero downside deviation or an interval without a declared annualization basis. |
| Expectancy | Arithmetic mean net P&L of completed trades. | Unavailable when there are no completed trades. |
| Turnover % | Gross simulated entry plus exit notional across completed trades divided by initial cash, multiplied by 100. | `0.0` when there are no completed trades. It is not a portfolio turnover calculation. |
| Exposure % | Marked equity-curve points with an open long position divided by all marked equity points, multiplied by 100. | Unavailable when no equity point exists. |
| Average holding period (days) | Arithmetic mean elapsed calendar days between each completed trade’s entry and exit timestamps. | Unavailable when there are no completed trades. |

## Immutable artifacts

`BacktestResult` now retains an equity-derived drawdown curve. Each `BacktestDrawdownPoint` records timestamp, marked equity, peak equity and drawdown percent. The curve is derived from existing simulated equity points; it does not change signals, fills, costs, cash, trades or the prior KPI calculations.

## Interpretation limits

The current engine is long-only, bar-based and uses next-bar fills with configured commission/slippage. It does not yet model portfolio-wide allocation, bid/ask spread, market impact, partial fills, dividend/corporate-action policy, margin, contract rolls or real data availability. These metrics must therefore be interpreted as local research outputs under explicitly stored assumptions, not as a prediction or deployment recommendation.

## Validation

```bash
make lint
make test
```

The metric suite covers numerical return/drawdown/trade/exposure context and verifies that insufficient history or missing trade context returns unavailable values instead of invented ratios.

This is research and analysis only, not personalized financial advice.
