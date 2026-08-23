# Local Paper Simulation with Central Risk Gate

## Scope

Phase 3B makes the local paper proposal path call the central risk engine before the existing local deterministic paper policy may evaluate a simulated submission. It does not connect a broker, authenticate an account, route an order, fetch market data, schedule a worker or enable live execution.

## Enforced submission sequence

```text
Fixture/reviewed proposal
        │
        ▼
OrderIntent + authoritative local context
        │
        ▼
CentralRiskEngine
   ┌────┼─────┐
   ▼    ▼     ▼
Allow Reject Defer
  │     │      │
  ▼     └──────┴─> append RISK_DECISION + ORDER_REJECTED
Legacy local paper policy
  │
  ├── reject ─────> append RISK_DECISION + ORDER_REJECTED
  │
  └── allow ──────> append RISK_DECISION + ORDER_SUBMITTED
                              │
                        explicit local fill only
                              │
                              └────> append ORDER_FILLED
```

`DEFER` is intentionally mapped to a blocked/rejected local paper proposal. The simulator does not guess missing availability/validation context or wait asynchronously for it to appear.

## Required central context

| Context | Local source in this phase | Effect when absent or unacceptable |
|---|---|---|
| Kill-switch state | Explicit local safety control | Central reject. |
| Prior order identities | Append-only paper ledger | Central duplicate reject. |
| Open-position count | Supplied local portfolio snapshot | Central limit reject when policy bound is reached. |
| Instrument status | Explicit normalized context | Central defer when absent or non-active. |
| Dataset validation outcome | Explicit accepted research evidence | Central defer when missing/quarantined/rejected. |

Only a central `ALLOW` reaches the existing local `DeterministicRiskPolicy`, which retains its own session count, daily loss, shorting, cash and notional controls.

## Append-only evidence

The existing `RISK_DECISION` event now records both local and central risk facts: final local allowed/code/reason, central policy version, central decision type, central decision code and central decision reason. Existing event types and local ledger ordering remain intact. The SQLite ledger now exposes distinct stored order identities so central duplicate detection is based on append-only local evidence rather than UI state.

## Fixture workbench

The Streamlit paper panel supplies an explicit fixture-only active-instrument and accepted-validation context for the selected batch. It remains a local event exercise with fixture marks. It must not be interpreted as broker-authoritative marks, a live paper gateway or a trade recommendation.

## Deferred work

Durable policy storage, a durable global kill state, portfolio/position projection, outstanding-order state, data freshness, broker-authoritative marks, reconciliation, broker gateway integration and all live execution controls remain out of scope. A later approved phase must add those controls before any broker integration could be considered.

## Validation

```bash
make lint
make test
```

The local paper tests cover central allow, reject, defer and ledger-derived duplicate outcomes while retaining explicit simulated fill behavior.

This is research and analysis only, not personalized financial advice.
