# Central Risk-Engine Foundation

## Scope

Phase 3A adds an independent, deterministic central risk-engine contract. It does not replace the current local paper service, persist policies, connect a broker, access an account, route an order or enable live trading. The purpose is to establish the fail-closed decision boundary that later paper and broker gateways must use.

## Decision model

| Decision | Meaning | Gateway behavior in a later phase |
|---|---|---|
| `ALLOW` | The supplied intent and all required context satisfy the named policy version. | A future paper gateway may proceed to its own lifecycle transition. |
| `REJECT` | A deterministic policy limit or global safety state prohibits the intent. | Do not submit; record the decision and reason. |
| `DEFER` | Required context is missing, inactive or not accepted. | Do not submit; request/reconcile authoritative context before reevaluation. |

Every decision includes the order ID, policy version, decision type, stable code and human-readable reason. The UI or a strategy cannot convert a reject/defer result to allow.

## Version 1 controls

| Rule | Outcome when triggered |
|---|---|
| Global kill switch active | `REJECT` / `KILL_SWITCH_ACTIVE` |
| Duplicate order-intent identity | `REJECT` / `DUPLICATE_INTENT` |
| Quantity exceeds policy | `REJECT` / `QUANTITY_LIMIT` |
| Notional exceeds policy | `REJECT` / `NOTIONAL_LIMIT` |
| Open-position count reaches policy limit | `REJECT` / `OPEN_POSITION_LIMIT` |
| Instrument context missing | `DEFER` / `INSTRUMENT_CONTEXT_MISSING` |
| Instrument not active | `DEFER` / `INSTRUMENT_NOT_ACTIVE` |
| Research validation missing | `DEFER` / `DATA_VALIDATION_MISSING` |
| Research validation not accepted | `DEFER` / `DATA_NOT_ACCEPTED` |

The engine is deterministic: the same `OrderIntent`, `CentralRiskPolicy` and `RiskEvaluationContext` return the same decision. It does not fetch, guess or repair context.

## Required boundary

```text
Signal or reviewed proposal
          │
          ▼
     OrderIntent
          │
          ▼
 CentralRiskEngine.evaluate(policy, authoritative context)
          │
     ┌────┼─────┐
     ▼    ▼     ▼
  Allow Reject Defer
     │    │     │
 future  audit  reconcile / supply required context
 paper   event
 gateway
```

The current `DeterministicRiskPolicy` in the paper MVP remains unchanged in this phase. A later approved integration phase must adapt the paper proposal path to the central engine and persist policy/decision/audit state using the defined event contracts.

## Deferred controls

Policy persistence, a durable kill switch, portfolio and order projections, outstanding-order limits, per-strategy/per-sector exposure, daily realised/unrealised loss, maximum drawdown, market session, data freshness, lot/tick enforcement, stop/target rules and reconciliation are not yet implemented by this foundation. They must be added in separately approved phases before any broker implementation or live-readiness work.

## Validation

```bash
make lint
make test
```

The contract suite proves deterministic allow decisions and fail-closed rejects/defers for kill, duplicate, limit, inactive, missing and quarantined context.

This is research and analysis only, not personalized financial advice.
