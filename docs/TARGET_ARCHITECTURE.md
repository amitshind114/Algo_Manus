# Target Architecture

## Purpose

This document defines the target shape for Algo Manus. It is a **contract and boundary specification**, not authorization to connect to a broker, ingest real market data, run a scheduler, deploy a service or place live orders.

The architecture preserves local-first, Windows-friendly research/paper operation while allowing future adapters to be added without contaminating the domain model or Streamlit views.

## Layering and dependency direction

```text
ui/ ───────────────► application/ ───────────────► domain/
                              │                       ▲
                              ▼                       │
                       infrastructure/ ───────────────┘

strategies/ ─────────────────────────────────────► domain/
```

| Layer | Responsibility | May depend on | Must not depend on |
|---|---|---|---|
| `domain/` | Immutable entities, values, event types, ports and deterministic business rules. | Python standard library and domain modules. | Streamlit, SQLite/Postgres drivers, HTTP, broker SDKs, provider SDKs or UI types. |
| `application/` | Use cases, orchestration, authorization of transitions, explicit command/result objects. | Domain and injected ports. | Direct SDK calls, UI state or storage-specific SQL. |
| `infrastructure/` | SQLite/Postgres implementations, migrations, local files, provider/broker adapters, structured logging. | Domain/application ports plus vendor libraries. | Streamlit state and strategy decision logic. |
| `strategies/` | Pure strategy plug-ins that validate parameters and turn `StrategyContext` into signals/intents. | Domain contracts. | Databases, HTTP, broker adapters, UI and execution paths. |
| `ui/` | Streamlit view components, input collection, presentation and application-use-case invocation. | Application result models and read models. | Strategy internals, database sessions, SDKs, risk-policy bypasses and direct execution. |

## Core bounded contexts

| Context | Owns | Essential contracts |
|---|---|---|
| Instrument and calendar | Canonical security/contract identity and tradability facts. | `Instrument`, `InstrumentMasterSnapshot`, `InstrumentAvailability`, `ExpiryResolver`, `OptionChainResolver`, `MarketSession`. |
| Market data and lineage | Validated observations, freshness and source evidence. | `MarketDataProvider`, `HistoricalDataProvider`, `LiveDataProvider`, `DatasetManifest`, `DataFreshness`, `DataQualityReport`. |
| Strategy and research | Strategy plug-ins, validated configuration and run proposal. | `StrategyMetadata`, `ParameterSchema`, `StrategyContext`, `Signal`, `StrategyRegistry`, `ResearchRunManifest`. |
| Backtesting and experiments | Deterministic replay, execution assumptions and immutable artifacts. | `BacktestRun`, `PortfolioBacktestRequest`, `ExecutionAssumptions`, `Experiment`, `ResultArtifact`. |
| Portfolio and risk | Event-derived holdings/P&L and policy evaluation. | `PortfolioSnapshot`, `RiskPolicy`, `RiskEngine`, `RiskDecision`, `RiskLimitSet`, `KillSwitchState`. |
| Execution and reconciliation | Intent-to-order lifecycle, fills and corrections. | `OrderIntent`, `Order`, `Fill`, `ExecutionEvent`, `ReconciliationResult`, `BrokerGateway`. |
| Operations and audit | Health, backups, logs, mode transition and non-secret audit trail. | `HealthProjection`, `AuditEvent`, `BackupService`, `RunCorrelation`, `OperationalMode`. |

## Strategy plug-in contract

The current pure SMA strategy remains the reference implementation. The target registry adds metadata and validation without giving a strategy any external authority.

| Contract | Required content | Safety rule |
|---|---|---|
| `StrategyMetadata` | Stable ID, display name, semantic version, author, description, risk notes, supported segments/instrument types/intervals. | Metadata is recorded into every run manifest. |
| `ParameterSchema` | Field name, type, range/options, default and cross-field validation rules. | The same schema validates UI input and programmatic requests. |
| `StrategyContext` | Validated dataset reference, instrument metadata, portfolio read model, clock, session and run correlation ID. | It exposes no repository/session/SDK handle. |
| `Signal` / `OrderIntent` | Decision, target/instrument, rationale code and causal run/strategy version IDs. | Neither may directly submit an order. |
| `StrategyRegistry` | Explicit registration/discovery API and lookup by stable strategy ID/version. | Unregistered or unsupported strategies fail validation. |

## Research and portfolio backtest architecture

Every persisted experiment begins with an immutable manifest. The engine reads a validated point-in-time dataset and a strategy version, then produces immutable artifacts.

```text
Validated data snapshot + Instrument snapshot + Strategy metadata/version
                         + Parameters + Engine & execution assumptions
                                     │
                                     ▼
                        Immutable ResearchRunManifest
                                     │
                                     ▼
                        Portfolio backtest application service
                                     │
                  ┌──────────────────┴──────────────────┐
                  ▼                                     ▼
          Event/trade stream                 Metrics and curves/artifacts
                  │                                     │
                  └──────────────► Experiment repository ◄──────────────┘
```

The run manifest must retain a Git commit SHA when available, strategy version, parameter revision, dataset ID/checksum, instrument snapshot ID, interval, date range, information cutoff, engine version, cost/slippage/spread/partial-fill assumptions, capital policy and creation time. A view may display derived statistics but cannot alter stored artifacts.

## Paper execution architecture

The paper path is a rehearsal of the future execution boundary. It shares canonical order and risk contracts but runs only with the local paper gateway until a separate approval exists.

```text
Strategy signal / user-reviewed proposal
                 │
                 ▼
            OrderIntent
                 │
                 ▼
      RiskEngine.evaluate(authoritative state, policy version)
                 │
        ┌────────┴────────┐
        ▼                 ▼
  Risk rejection     PaperExecutionGateway
  + audit event              │
                              ▼
              Immutable order/fill/cancel/reconciliation events
                              │
                              ▼
                   Portfolio and P&L projections
```

| Lifecycle state | Meaning | Position/P&L effect |
|---|---|---|
| `CREATED` | Intent accepted for policy evaluation. | None. |
| `RISK_REJECTED` | Central risk engine denied it with reason code. | None. |
| `SUBMITTED` / `ACKNOWLEDGED` | Gateway accepted the request for paper processing. | None. |
| `PARTIALLY_FILLED` | One or more fill events applied. | Only filled quantity affects positions/P&L. |
| `FILLED` | Remaining order quantity filled. | Event-derived projection updates. |
| `CANCELLED` / `REJECTED` / `FAILED` | Terminal non-fill state. | None beyond prior fills. |
| `RECONCILED` | Local projection compared/corrected through a new immutable event. | Correction is additive/auditable, never a hidden rewrite. |

## Persistence and portability

SQLite remains the default local store. Repository interfaces live at the domain/application boundary so future Postgres support is an infrastructure replacement rather than a domain rewrite. Each write path must use versioned migrations, bounded connection lifetimes, explicit transaction scope, stable serialization and deterministic cleanup.

| Repository family | Minimum durable entities |
|---|---|
| Instrument/data | Instrument snapshots, mappings, availability evaluations, dataset manifests, quality/freshness reports. |
| Research | Strategy registrations/configurations, immutable manifests, experiments, results, curves, trades and review state. |
| Execution | Policies, kill-switch changes, intents, orders, fills, audit events, projections and reconciliation outcomes. |
| Operations | Migrations, backup manifests, health observations, structured error metadata and recovery acknowledgements. |

## Integration boundary

No production adapter is included in the target architecture phase. Future adapters must conform to ports such as `InstrumentMasterProvider`, `HistoricalDataProvider`, `LiveDataProvider`, `BrokerGateway` and `OrderExecutionGateway`. Test doubles remain the first implementation of each port.

All adapters must translate transport/vendor errors into explicit domain/application errors, enforce timeouts/retries/rate limits at the boundary, avoid logging credentials, preserve provider/source identity, and be disabled in all unapproved modes.

## Mode model

| Mode | Permitted behavior | Prohibited behavior |
|---|---|---|
| `DEMO` | Deterministic synthetic data and workflow testing. | Market claims, broker calls, performance claims or live controls. |
| `RESEARCH` | Approved historical research data, strategy configuration and backtesting. | Paper/live order submission. |
| `PAPER` | Risk-gated simulated proposals/orders/fills with explicit data-policy checks. | Live broker submission. |
| `LIVE` | Future explicitly approved bounded pilot only. | Automatic activation, UI-only activation, missing reconciliation or bypassed risk policy. |

`LIVE` is not merely a label. It remains unavailable until an independent live-readiness record confirms all preconditions from the master delivery plan.[1]

## References

[1]: ./MASTER_DELIVERY_PLAN.md "Existing master delivery plan"
