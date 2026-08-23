# Local Portfolio Risk Snapshot

## Scope

Phase 5A adds a **local, fixture-marked portfolio-risk snapshot** to the central paper risk gate. The snapshot is derived from the durable local paper replay, not from a broker account, market-data feed, exchange mark, clearing record or reconciliation process.

## Derived local facts

| Fact | Source | Use in central risk evaluation |
|---|---|---|
| Open local positions | Durable local paper-event replay | Existing open-position count and per-instrument exposure. |
| Fixture gross exposure | Sum of `abs(local quantity) × explicit fixture mark` | Aggregate exposure control. |
| Fixture instrument exposure | Per-instrument `abs(local quantity) × explicit fixture mark` | Per-instrument and concentration controls. |
| Realised P&L | Durable local paper replay | Local realised-loss control. |
| Order notional | Proposed local fixture intent | Projected gross/instrument exposure and concentration. |

The workbench applies the selected fixture mark to the selected instrument. Any other held local positions use their replayed average-entry price as an explicit local fallback mark. This is a deterministic UI convention for testing local controls only; it is **not** a quote, end-of-day price, NAV, broker valuation or reconciliation value.

## Versioned central policy controls

The central policy continues to enforce kill state, duplicate identity, instrument availability, accepted dataset evidence, quantity, per-order notional and open-position limits. Version 2 policy storage additionally supports these optional controls:

| Control | Decision condition | Result |
|---|---|---|
| Maximum gross notional | Projected total fixture exposure is above the configured cap. | `REJECT / GROSS_EXPOSURE_LIMIT` |
| Maximum instrument notional | Projected exposure for the intent instrument is above its cap. | `REJECT / INSTRUMENT_EXPOSURE_LIMIT` |
| Maximum realised loss | Derived local realised P&L is at or below the negative loss cap. | `REJECT / REALIZED_LOSS_LIMIT` |
| Maximum concentration | Projected intent-instrument exposure divided by projected gross exposure is above the cap. | `REJECT / CONCENTRATION_LIMIT` |

When a configured policy requires portfolio controls but no snapshot is available, the engine fails closed with `DEFER / PORTFOLIO_RISK_CONTEXT_MISSING`.

## Evaluation order

The engine checks safety and input validity first, then order-specific limits, then portfolio-level limits. This deterministic order means a single invalid proposal yields one stable decision code rather than an ambiguous list of possible failures.

## Local storage compatibility

The local risk-control SQLite component migrates from schema version 1 to version 2 by adding nullable portfolio-limit columns. Existing version-1 policies therefore retain their original per-order/open-position behavior and do not silently acquire portfolio limits. The fixture workbench uses a new `fixture-central-risk-v2` policy record for Phase 5A controls.

## Explicit limitations

No broker account balance, margin, pledged collateral, realised tax, corporate action, external mark, market session, settlement, multi-account allocation or broker reconciliation is available. These controls are suitable only for exercising local research and local paper workflow invariants. Broker data, real paper observation and any live execution remain separately gated.

## Validation

```bash
make lint
make test
```

Regression coverage includes fixture-marked risk derivation, missing-mark fail-closed behavior, each portfolio-limit decision, missing snapshot deferral and version-1 SQLite migration.

This is research and analysis only, not personalized financial advice.
