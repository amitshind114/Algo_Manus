# India Algo Platform

> **Status: local research and paper workbench.** Algo Manus contains deterministic local components for India-market research, retained evidence inspection, and paper operations. Live execution remains unavailable unless separately approved data, risk, execution, security, and operational gates are completed.

## Product description

Algo Manus is an India-first local research, analytics, evidence, and paper-operations platform for **NSE/BSE cash equities** and **NFO listed derivatives**. It is designed for users who require transparent research workflows, reproducible backtests, bounded paper simulation, observable risk controls, and a deliberate approval path before any future live-execution work.

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

## Current implementation

The assembled local platform includes:

| Local capability | Current implementation boundary |
|---|---|
| Instruments and datasets | India-first lifecycle contracts, immutable source-aware datasets, validation, local SQLite retention, and explicit stale/change review states. |
| Research and backtesting | Versioned strategy and parameter revisions, next-bar semantics, declared costs/slippage, reproducible experiment specifications, artifact integrity, and multi-security KPI projections. |
| Evidence and reporting | Retained research manifests, robustness and dataset-review evidence, paper-run eligibility evidence, cross-evidence linkage, freshness coverage, canonical exports, and read-only manifest comparison. |
| Paper operations | Deterministic risk decisions, durable kill-switch controls, local limit-fill simulation, append-only event evidence, projections, audit timelines, and operations-console reads. |
| Workbench | A thin Streamlit research-and-paper interface that invokes application services only and displays retained evidence without direct provider or database calls. |

The workbench uses local sample datasets where retained broker historical datasets are not present. Sample results are clearly labelled in context and are not broker data, live market evidence, performance proof, or recommendations.

## Operating guides

The current workbench and operating boundaries are documented in [`docs/LOCAL_APP.md`](docs/LOCAL_APP.md), [`docs/LOCAL_LIMITATIONS.md`](docs/LOCAL_LIMITATIONS.md), and [`docs/READINESS_GATES.md`](docs/READINESS_GATES.md). Architecture and service responsibilities are described in [`docs/ARCHITECTURE_PRINCIPLES.md`](docs/ARCHITECTURE_PRINCIPLES.md), while individual evidence, risk, paper, and retained-artifact contracts are documented alongside their corresponding local capabilities in `docs/`.

## Verification

Run `make lint` to compile source and tests, and `make test` for the deterministic test suite.

This is research and analysis only, not personalized financial advice.
