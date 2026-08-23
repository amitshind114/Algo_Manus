# Canonical Instruments and Execution Contracts

## Scope

Phase 1B adds shared vocabulary only. It does **not** add a provider adapter, broker connection, market-data request, option-chain download, paper-service rewrite, background runner or live-order capability.

The contracts make later research, portfolio, risk and paper-execution work speak the same immutable language while retaining the current local fixture workflow.

## Derivative-ready instrument vocabulary

The canonical `Instrument` retains stable identity from broker, exchange, segment and broker token. Display names and trading symbols remain descriptive fields and must never be used as a replacement identity.

| Instrument type | Required contract fields | Validation behavior |
|---|---|---|
| Equity/index/commodity | Broker, exchange, segment, token, trading symbol, type and active status; lot/tick values when supplied. | Retains existing snapshot behavior. |
| Future | All core fields plus expiry, positive lot size and positive tick size. | Invalid/incomplete derivative record fails before it enters a snapshot. |
| Option | Future requirements plus positive strike and call/put option type. | Strike or option type on a non-option record fails explicitly. |

`contract_descriptor` is a display-safe future/option description. It is not an identifier and cannot be used to map an expired, renamed or changed broker contract.

## Generic order lifecycle

The new execution types are provider-neutral and distinct from the current local `PaperOrder` types. They are the target vocabulary for a later refactor; current paper behavior remains unchanged.

| Status | Meaning | Position/P&L consequence |
|---|---|---|
| `CREATED` | An immutable intent has become an order projection awaiting policy/execution transition. | None. |
| `RISK_REJECTED` | Central policy denied the intent. | None. |
| `SUBMITTED` / `ACKNOWLEDGED` | Future gateway acceptance states. | None. |
| `PARTIALLY_FILLED` | One or more valid fill events recorded. | Only a future portfolio projection may apply actual fill quantities. |
| `FILLED` | Filled quantity equals original order quantity. | Same rule: fill events, not submission state, are the evidence. |
| `CANCELLED` / `REJECTED` / `FAILED` | Terminal non-fill/failed states. | None beyond any already-recorded fills. |
| `RECONCILED` | A later reconciliation outcome was recorded. | Non-destructive correction workflow; no hidden history rewrite. |

An `ExecutionOrder` is an immutable lifecycle projection. `Fill` is an immutable quantity/price/time record. Neither contains position or P&L fields. Portfolio and P&L projections belong to the approved future portfolio/risk phase and must derive only from append-only fills/reconciliation records.

## Repository ports

The contracts declare four storage ports only: `OrderRepository`, `FillRepository`, `ExecutionEventRepository` and `ReconciliationRepository`. No SQLite schema or implementation has been added in this phase. This keeps the port boundary clear and avoids silently changing the current append-only local paper ledger.

## Validation evidence

The contract suite rejects incomplete option/future metadata, invalid status transitions, wrong fill identity/side, fill quantities exceeding the order and timezone-naive lifecycle/reconciliation records. It also verifies that a partial fill and final fill create new immutable order projections and that generic orders do not include a P&L field.

## Next dependency

The next safe phase is to add **portfolio and central RiskEngine foundation contracts** that consume these types while retaining a paper-only, default-deny safety posture. No broker gateway is part of that next phase.

This is research and analysis only, not personalized financial advice.
