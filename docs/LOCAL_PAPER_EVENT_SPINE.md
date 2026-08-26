# Local Paper Event Spine

## Purpose and Scope

Option E establishes one **append-only, local-only paper-event spine** for simulated research operations. The SQLite paper ledger remains the retained source of event evidence. Position quantity, average entry, cash, realised P&L, order state and reconciliation disposition are all **derived by replay**; they are not stored as authoritative mutable portfolio records.

> A retained paper event is evidence of a local simulation step. It is never a broker acknowledgement, a venue order, a market fill, a live position, a cash balance, or proof of reconciliation.

| Stage | Retained event | Derived lifecycle effect | Portfolio effect |
| --- | --- | --- | --- |
| Proposal | `ORDER_PROPOSED` | `PENDING_RISK` | None |
| Deterministic gate | `RISK_DECISION` | `RISK_APPROVED` only when `allowed=true` | None |
| Local acceptance or denial | `ORDER_ACCEPTED` / `ORDER_REJECTED` | `ACCEPTED` / `REJECTED` | None |
| Local working state | `ORDER_WORKING` | `WORKING` | None |
| Simulated execution | `ORDER_PARTIALLY_FILLED` / `ORDER_FILLED` | `PARTIALLY_FILLED` / `FILLED` | Applies only retained fill quantity and retained fill price |
| Local close-out | `ORDER_CANCELLED` | `CANCELLED` | None; unfilled remainder stays unfilled |
| Evidence comparison | `RECONCILIATION_RECORDED` | `RECONCILED` | None; it adds a disposition and reason only |

## Risk-First Rule

Every new local paper intent records `ORDER_PROPOSED`, then one structured `RISK_DECISION`, before the service can append `ORDER_ACCEPTED`. A denied or deferred decision records `ORDER_REJECTED` and cannot create accepted, working or fill evidence. Existing retained `ORDER_SUBMITTED` events remain readable as a legacy compatibility event and project to the current `ACCEPTED` local state only after retained allowed-risk evidence.

The central deterministic risk engine remains the gate. The event payload captures the evaluated decision, central policy version, durable kill-switch evidence where configured, and research-promotion identifiers where required. A duplicate order identity is rejected without opening a second event stream for the same local order ID.

## Fill and Projection Semantics

Each simulated fill carries its own quantity, fill price and `cumulative_filled_quantity`. Replay accepts a partial-fill event only when its cumulative quantity is strictly between zero and the original retained order quantity. A final fill must close the entire remaining quantity. Duplicate, out-of-order, missing-risk, excessive or malformed evidence is retained but listed as **unprojectable**; replay does not repair, reorder, delete or financially apply it.

The projection is long-only. A simulated sell that exceeds the derived local position is unprojectable and is not applied. The explicit starting cash must be supplied to the read service. Replaying the same retained event sequence after an application or SQLite restart produces the same cash, positions, realised P&L and local order projection.

## Reconciliation Semantics and Limits

`RECONCILIATION_RECORDED` may be appended only to a terminal local simulation order. It retains one local disposition — `MATCHED`, `CORRECTED`, or `UNRESOLVED` — and a required local reason. It does **not** alter prior events, create a correction fill, change cash, modify position quantity, or prove agreement with any broker record.

There is no broker-account, holdings, positions, funds, order-history, trade-book, market-price, feed, WebSocket, scheduler or reconciliation-data connection in this slice. Consequently, Option E supports reconciliation **evidence structure**, not external reconciliation. Any future broker comparison must be separately approved, data-sourced, retained, matched by explicit identifiers and implemented as additional append-only evidence without silently mutating local projections.

## Local Workbench Views

The **Risk & paper** page uses application read services to display retained events, event-derived positions, projected cash, realised P&L, order fill totals, remaining quantity, reconciliation evidence and audit-integrity state. The timeline can filter retained event and derived lifecycle categories, including proposal, risk decision, acceptance, working, partial fill and reconciliation evidence. Those controls are display-only and cannot reconcile, repair, amend, cancel, route or submit any order.

## Explicit Exclusions

Option E adds no broker endpoint and no new external integration. It does not add live execution, a paper broker, external price discovery, autonomous fills, account or portfolio retrieval, scheduled processing, cloud processing, WebSockets, alerts or investment recommendations. The only simulated fills are explicit local service calls with caller-supplied values that remain visibly local simulation evidence.

This is research and analysis only, not personalized financial advice.
