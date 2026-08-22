# India Algo Platform

> **Status: foundation planning.** This repository starts as a research and paper-trading platform for Indian listed markets. It will not submit live orders until its data, risk, execution, security and operational controls have passed separately defined readiness gates.

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

The documentation-first structure will evolve into the following modules only after the roadmap gates are approved.

```text
india-algo-platform/
├── docs/                 # Charter, roadmap, architecture and control decisions
├── services/
│   ├── instrument-data/  # Instrument master, session calendar and data lineage
│   ├── research/         # Strategy specifications, backtest orchestration and evidence
│   ├── risk/             # Deterministic pre-trade policy and exposure controls
│   ├── paper-execution/  # Simulated order lifecycle and reconciliation events
│   └── execution/        # Future, separately approved live execution boundary
├── packages/
│   ├── domain/           # Canonical typed domain contracts
│   ├── event-ledger/     # Durable order/fill/reconciliation event model
│   └── ui/               # Research and operations user-interface primitives
├── tests/                # Deterministic fixtures and contract/integration tests
└── infrastructure/       # Environment, security and deployment-as-code definitions
```

## Safety and compliance posture

This is an engineering and research repository, not a signal-selling, advisory or portfolio-management product. Before any live pilot, the project must complete a documented review of applicable exchange, broker, data-provider, information-security, privacy and legal requirements. The design will preserve a paper-only default and an explicit “no-live-execution” gate until a controlled pilot is separately approved.

## Next milestone

The first repository commit consists only of this product description and the phased roadmap in [`docs/ROADMAP.md`](docs/ROADMAP.md). After the documentation gate, the next proposed work is to define canonical domain contracts and an executable-free data/instrument research skeleton.

## Research basis

The roadmap is informed by the completed cumulative workbook at `indian_market_repo_knowledge.xlsx` and the reviewed repository assessments. The source program assessed reuse potential, not strategy profitability, and retained MIT/third-party licence boundaries. No reviewed repository is being adopted wholesale.

This is research and analysis only, not personalized financial advice.
