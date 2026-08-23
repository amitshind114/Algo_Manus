# Strategy Registry and Extension Boundary

## Purpose

Algo Manus now has a small, explicit registry for locally available research strategies. It replaces implicit strategy selection with a stable contract that a future Strategy Lab and experiment manifest can use without letting a strategy access data providers, storage, UI state, a paper gateway or a broker.

## Current registered implementation

| Strategy ID | Version | Supported instrument type | Supported interval | Status |
|---|---|---|---|---|
| `sma_crossover` | `1.0.0` | `EQUITY` | `1d` | Reference implementation for deterministic fixture research. |

The current registry is deliberately explicit and in-process. It does not scan the filesystem, load third-party code dynamically or import a broker/provider plug-in. This keeps the local research path deterministic and auditable while plug-in governance is still being established.

## Required strategy contract

Every registered strategy declares immutable display-safe metadata and a strict parameter schema.

| Contract | Why it exists |
|---|---|
| Stable strategy ID and semantic version | Lets a future immutable run manifest identify the exact decision logic. |
| Display name, author, description and risk notes | Makes the research UI informative without inventing performance claims. |
| Supported instrument types and intervals | Rejects invalid research configuration before a run starts. |
| Parameter schema | Validates required fields, types, bounds and cross-field constraints consistently for UI and application callers. |
| Pure signal methods | Preserves the rule that strategies cannot place orders or access infrastructure. |

The `StrategyContext` type is an intentionally read-only future-facing contract for validated candles, instrument facts, portfolio read state and a timezone-aware clock. It contains no repository, SDK, network or execution handle.

## Safe extension workflow

1. Implement the pure strategy under `src/algo_manus/strategies/`.
2. Declare `StrategyMetadata` with a stable ID/version, supported scope, risk notes and `StrategyParameterSchema`.
3. Add the strategy to the explicit built-in registry only after tests cover metadata, schema validation, compatibility and deterministic signal behavior.
4. Add a backtest regression fixture before wiring the strategy into any UI view.
5. Keep all output at the `Signal`/`OrderIntent` boundary. A future paper proposal must still pass the central risk engine.

> A registered strategy is a research component, not an endorsement, a profitability claim, a broker integration or permission to execute an order.

## Validation commands

```bash
make lint
make test
```

The registry contract suite rejects duplicate IDs, unknown strategies, undeclared instrument/interval combinations, missing/unknown parameters, non-integer SMA windows and invalid SMA cross-field configurations.

This is research and analysis only, not personalized financial advice.
