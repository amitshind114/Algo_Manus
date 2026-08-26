# Event-Derived Local Paper-Operations Console

## Purpose

Option H consolidates existing local evidence into one read-only paper-operations console. It does not introduce an order-management system, broker dashboard, monitoring service, account view, market-data terminal, real-time control plane, or execution path.

> The console is a projection. It does not own or modify order state. Its authoritative inputs remain immutable local paper-ledger events, the local paper replay, the local audit interpreter, and the bounded current-process wiring audit.

## Evidence inputs and derived fields

| Console area | Evidence source | Derived fields | Explicit non-claim |
| --- | --- | --- | --- |
| Portfolio projection | Immutable local `PaperEvent` replay. | Starting cash, projected cash, realised P&L, open positions, order quantities and fill totals. | Not a broker account, ledger balance, venue position, live valuation or reconciliation proof. |
| Lifecycle summary | Event-derived paper-order projection. | Count by retained projected lifecycle status. | Not an exchange/broker order-status feed. |
| Risk summary | Most recent interpretable retained `RISK_DECISION` audit row. | Local allow/deny decision, central decision type/code. | Not an active broker RMS, compliance control result or recommendation. |
| Simulator summary | Retained local simulation evidence in paper audit rows. | Count of local `NO_FILL`, `PARTIAL_FILL` and `FILLED` outcomes. | Not quote, volume, order-book, queue or venue-fill evidence. |
| Reconciliation summary | Reconciliation disposition retained on projected local terminal paper orders. | Count by local disposition. | Not broker or cash/position reconciliation proof. |
| Integrity summary | Paper audit interpretation and replay diagnostics. | Retained-event total, valid interpretation total and malformed/invalid-state evidence. | It does not repair, remove or amend evidence. |
| Wiring diagnostics | Current-process bounded local event-bus audit. | Retained event/delivery count, failed-delivery count, registered local subscriber names. | Non-durable and empty after process restart; not a queue, log, consumer service or delivery guarantee. |

## Safety and restart semantics

The console reads local paper and wiring evidence only. It exposes no submit, fill, cancel, reconcile, publish, subscribe, retry, replay, synchronization, repair, export, broker, account, venue, price-feed, WebSocket, scheduler, worker, cloud, paper-broker or live-execution action.

Malformed or out-of-sequence retained paper events remain visible as integrity/replay diagnostics. They do not prevent the console from showing valid retained evidence or projection state. Current-process wiring diagnostics are intentionally non-durable and will not be reconstructed from the durable ledger after restart.

The console appears in **Risk & paper**. It centralizes its tiles and the nearby event table through one application read service; the workbench does not calculate lifecycle, P&L, simulator, reconciliation or wiring state itself.

This is research and analysis only, not personalized financial advice.
