# Local Conservative Limit-Fill Simulator

## Scope

Option F adds a deterministic **local-only** fill model on top of the immutable Option E paper-event spine. The model accepts explicit caller-supplied assumptions, records its decision in the local SQLite paper ledger, and projects cash and long-only positions from retained simulated fill events only.

> A simulator outcome is local evidence of declared assumptions. It is not a broker quote, traded volume, queue position, exchange acknowledgement, venue fill, market-data observation, account record, or reconciliation proof.

## Required local assumptions

| Input | Rule | Retained evidence meaning |
| --- | --- | --- |
| Order type | Must be `LIMIT`; a `MARKET` assumption is rejected before appending a new event. | The local model does not accept market-order simulation. |
| Limit price | Must be positive. | The highest local buy fill or lowest local sell fill allowed by the selected assumption. |
| Observed price | Must be positive and supplied by the caller. | A local simulation input, never a fetched or broker-supplied price. |
| Available quantity | Must be zero or positive. | A caller-declared local volume cap, not traded volume or order-book liquidity. |
| Adverse slippage | Must be zero or positive basis points. | A deterministic adverse adjustment to the local observed price. |
| Session-open flag | Boolean and supplied by the caller. | A local scenario flag, not exchange calendar validation. |
| Model version | Required non-empty identifier. | Version of the retained local assumption model. |

For a buy, the simulator applies adverse slippage upward to the observed price and permits a fill only when that effective local price is at or below the limit. For a sell, it applies adverse slippage downward and permits a fill only when the effective local price is at or above the limit. The effective result is rounded deterministically to ten decimal places for stable replay.

## Decision behavior

| Condition | Retained event | Local lifecycle / portfolio effect |
| --- | --- | --- |
| Non-limit order assumption | No new event; the application service raises a validation error. | No lifecycle or portfolio change. |
| `session_open=false` | `ORDER_UNFILLED` with `SESSION_CLOSED`. | The order remains actionable; no cash, position, or P&L change. |
| Effective local price violates the limit | `ORDER_UNFILLED` with `LIMIT_NOT_ELIGIBLE`. | The order remains actionable; no cash, position, or P&L change. |
| Available local quantity is zero | `ORDER_UNFILLED` with `NO_AVAILABLE_SIMULATED_VOLUME`. | The order remains actionable; no cash, position, or P&L change. |
| Eligible local quantity is below remaining order quantity | `ORDER_PARTIALLY_FILLED` with `VOLUME_CAPPED`. | Only the retained partial quantity changes replayed cash and position. |
| Eligible local quantity covers the remaining order quantity | `ORDER_FILLED` with `FILLED_WITH_EXPLICIT_LOCAL_ASSUMPTIONS`. | Only the retained final quantity changes replayed cash and position. |

The model does not infer a fill from an order intent, UI state, strategy output, or backtest result. It first relies on the existing Option E risk-first accepted lifecycle and then appends explicit local simulator evidence.

## Safety and reconciliation limits

The read-only audit timeline exposes the retained local simulator outcome, reason, model version, limit price, observed price, available quantity, adverse-slippage input, and session flag. This makes it possible to inspect a no-fill or partial-fill result without treating it as external confirmation.

Cancellation, duplicate-request rejection, restart-safe replay, and non-destructive reconciliation evidence remain supported by the Option E event spine. A reconciliation disposition can document a local comparison state, but it does not connect to a broker or venue, mutate an event, apply a correction fill, or make a paper result externally verified.

## Explicit exclusions

Option F adds no broker endpoint, account query, holdings/positions/funds query, LTP feed, historical or live market-price request, order-book feed, WebSocket, scheduler, background worker, paper broker, cloud service, alerting system, or live execution path. It makes no queue-position, latency, volume, slippage, limit-fill, paper-performance, or live-executability claim beyond its explicit local inputs.

This is research and analysis only, not personalized financial advice.
