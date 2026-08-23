# India Algo Platform

> **Status: local research and paper foundation.** This repository contains deterministic, fixture-tested local components for India-market research and paper operations. It will not submit live orders until separately defined data, risk, execution, security and operational gates are approved.

## Product description

India Algo Platform is intended to become an India-first, end-to-end research, analytics and execution-control foundation for **NSE/BSE cash equities** and **NFO listed derivatives**. Its first users are disciplined individual and professional research teams who need transparent research workflows, reproducible backtests, paper trading, observable risk controls and a deliberate path to broker-approved live execution.

The platform is being designed from a static review program covering 58 GitHub repositories and a cross-repository synthesis. The program found reusable ideas in broker abstractions, India-market workflows, research models, risk concepts, paper-trading interfaces and dashboards. It also established that production readiness cannot be achieved by combining open-source bots: data lineage, instrument masters, point-in-time research, reconciliation, security, compliance and controlled execution must be designed as first-class systems.

## First-release scope

The initial release is **research and paper trading only**. It will support data provenance, India-market instruments and sessions, a strategy research workspace, reproducible backtest specifications, non-executable trade proposals, a deterministic risk-policy service, simulated order lifecycles and operational monitoring. It will not connect user brokerage accounts, submit orders, store broker credentials or make personalized investment recommendations.

| Included in the first release | Explicitly excluded from the first release |
|---|---|
| Research datasets and source/freshness metadata | Live broker authentication or account access |
| NSE/BSE/NFO instrument, contract and session models | Live order submission, cancellation or modification |
| Strategy definitions and backtest specifications | Autonomous LLM-driven execution |
| Paper-order simulation and reconciliation-style event models | Customer money, custody, payments or portfolio management |
| Deterministic pre-trade policy evaluation | Claims of profitability or performance guarantees |
| Human-reviewed research and trade proposals | FX 24/5 and crypto 24/7 execution support |

## Design principles

The platform will be **India-first but venue-extensible**. Exchange sessions, expiries, lot sizes, tick sizes, corporate actions and derivative contract lifecycles will be explicit domain data rather than scattered constants. A later FX or crypto module must implement its own venue/session/margin semantics through the same canonical interfaces; it must not inherit India-market defaults.

The platform will be **evidence-first**. Every material research input should retain its source, retrieval time, market/session context, symbol/contract mapping, adjustment basis and freshness status. Backtest results will be treated as experiments with an immutable specification—not as performance proof.

The platform will be **risk-first and execution-separated**. Research, LLM assistance, user interfaces and execution controls will have distinct responsibilities. A deterministic policy service will own hard constraints. No live order can be inferred from an LLM response or a user-interface button without independent authorization, validated market/instrument/account state and a durable audit trail.

The platform will be **reconciliation-first**. An order intent, broker submission, broker acknowledgement, exchange state, partial fill, complete fill, cancellation and rejection are different events. Positions, P&L and risk should be derived from reconciled events rather than a local record of requested orders.

## Repository layout

The current local build uses a deliberately small Python structure. Interfaces remain thin and provider/database/UI dependencies stay outside the domain layer.

```text
india-algo-platform/
├── src/algo_manus/
│   ├── domain/           # Canonical instruments, data, strategy, risk, paper and operations contracts
│   ├── application/      # Sync, research, backtest, leaderboard, paper and health use cases
│   ├── infrastructure/   # Local SQLite repositories, audit trail and future provider ports
│   ├── strategies/       # Pure, versioned strategy implementations
│   └── ui/               # Optional thin Streamlit local shell
├── tests/                # Deterministic fixtures, contracts and local workflow tests
└── docs/                 # Roadmap, local use, limitations and approval gates
```

## Safety and compliance posture

This is an engineering and research repository, not a signal-selling, advisory or portfolio-management product. Before any live pilot, the project must complete a documented review of applicable exchange, broker, data-provider, information-security, privacy and legal requirements. The design will preserve a paper-only default and an explicit “no-live-execution” gate until a controlled pilot is separately approved.

## Current implementation status

The repository now includes the high-level [`docs/ROADMAP.md`](docs/ROADMAP.md), detailed ten-phase [`docs/MASTER_DELIVERY_PLAN.md`](docs/MASTER_DELIVERY_PLAN.md) and implemented [`docs/PHASE_1_FOUNDATION.md`](docs/PHASE_1_FOUNDATION.md). The assembled local foundation includes:

| Local capability | Current implementation boundary |
|---|---|
| Instrument master and universes | Immutable broker-normalized snapshot contracts, stale/master-change detection and validated selection. |
| Market data | Source-aware candle contracts, local SQLite datasets and policy rules that block non-broker data in paper/risk contexts. |
| Research/backtesting | Versioned parameter revisions, an explicit next-bar-fill SMA reference strategy, cost/slippage assumptions and reproducible specifications. |
| Multi-security comparison | Persisted experiment batches and core-engine KPI leaderboard projections. |
| Paper operations | Deterministic risk decision, kill-switch rejection, simulated fill state and append-only local event ledger. |
| Local operations | Optional disabled-by-default Streamlit shell, audit redaction and health projection. |

All current execution paths use fixtures and local SQLite only. The integrated workflow test proves the local contract flow, not provider or strategy performance.

## Local MVP workflow and preview

The product-facing local research and paper-trading workflow is documented in [`docs/LOCAL_MVP_WORKFLOW.md`](docs/LOCAL_MVP_WORKFLOW.md). The local UI instructions are in [`docs/LOCAL_APP.md`](docs/LOCAL_APP.md), operational controls are in [`docs/LOCAL_OPERATIONS.md`](docs/LOCAL_OPERATIONS.md), current limitations are in [`docs/LOCAL_LIMITATIONS.md`](docs/LOCAL_LIMITATIONS.md), and separately approved next gates are in [`docs/READINESS_GATES.md`](docs/READINESS_GATES.md).

## Research basis

The roadmap is informed by the completed cumulative workbook at `indian_market_repo_knowledge.xlsx` and the reviewed repository assessments. The source program assessed reuse potential, not strategy profitability, and retained MIT/third-party licence boundaries. No reviewed repository is being adopted wholesale.

This is research and analysis only, not personalized financial advice.
