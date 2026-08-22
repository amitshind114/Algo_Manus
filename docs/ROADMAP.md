# Implementation Roadmap

## Purpose

This roadmap converts the repository-research program into a controlled build sequence for an India-first trading platform. It deliberately separates research, paper execution and any future live execution. A phase can advance only when its stated evidence and control gates are satisfied.

## Delivery sequence

| Phase | Primary outcome | Initial deliverables | Gate to proceed |
|---:|---|---|---|
| 0 | Product charter | This roadmap, product description, decision log and repository conventions | Owner agrees the platform is research/paper-only initially and approves the architecture principles |
| 1 | Canonical domain foundation | Typed instruments, exchange sessions, derivative contracts, orders, fills, positions, portfolios, risk decisions and data-source metadata | Contract tests cover India equity/F&O cases, and no module can submit a live order |
| 2 | Data and instrument lineage | Versioned instrument masters, NSE/BSE/NFO calendars, expiry/holiday rules, source/freshness records, data-quality rules and cache policy | Every research dataset can be traced to source, timestamp, schema/version and symbol/contract identity |
| 3 | Research and validation engine | Strategy specification format, point-in-time experiment inputs, costs/slippage/taxes interface, out-of-sample workflow, backtest result registry | A deterministic sample experiment runs only from approved fixtures/datasets and records a reproducible specification |
| 4 | Paper execution and risk controls | Deterministic policy engine, paper-order state machine, simulated fills, broker-style rejects, multi-leg lifecycle, reconciliation events and risk dashboard | Simulated orders pass end-to-end lifecycle/recovery tests; risk limits are derived from reconciled events, not local request records |
| 5 | Operations and secure user workflows | Authentication/roles, secrets boundary, audit logs, alerts, monitoring, incident runbooks and research operations UI | Security, observability and access-control reviews approve a paper-pilot environment |
| 6 | Separately approved live-pilot preparation | Broker-specific connector design, official OAuth architecture, encrypted token handling, idempotency, broker reconciliation, native protection and human approvals | Legal/compliance, broker/data rights, security review, disaster recovery and controlled pilot acceptance are explicitly approved |

## Phase 0: documentation and governance

Phase 0 produces the repository’s durable design basis. It records the first-release boundary, non-goals, architecture principles, evidence standards and decision log. It does not create any broker credentials, network listener, data-provider connector or execution code.

The output is ready for commit when the repository owner has accepted the scope, selected a licence and confirmed the default branch/visibility. The initial commit is documentation only.

## Phase 1: canonical domain foundation

The platform needs a stable shared vocabulary before services are built. The initial types will cover venue, exchange session, instrument, underlying, cash equity, futures contract, options contract, quote, market-data observation, strategy specification, research evidence, order intent, broker submission, acknowledgement, fill, cancellation, rejection, position, realised/unrealised P&L and risk decision.

The most important rule is that **an order request is not a fill**. The model will represent every state change as a typed event with an event time, source, correlation/causation ID and immutable payload. India-specific details such as NFO expiry, lot and tick rules will come from versioned data, not hard-coded strategy logic.

## Phase 2: data and instrument lineage

Research quality depends on the ability to replay decisions using the same point-in-time inputs. This phase creates data-source registration, freshness policy, schema/version tracking, source-retrieval metadata, corporate-action/adjustment declarations and session-aware instrument resolution. It also establishes a broker/data-provider abstraction that does not expose credentials to strategy or LLM code.

The platform must reject or visibly label degraded sources in contexts where stale or fallback data is not permitted. The exact data sources and rights will be selected only after provider, usage-right and coverage analysis.

## Phase 3: research and validation engine

This phase treats backtests as experiments. A strategy has a versioned hypothesis, parameters, universe definition, information cutoff, data version, execution/cost assumptions, session rules and evaluation window. The engine will support unit tests, deterministic fixtures, walk-forward/out-of-sample workflows and result lineage.

No result will be labelled production-ready merely because it has a favourable return, Sharpe ratio or win rate. Selection requires documented robustness, data-quality evidence, conservative execution assumptions and independent review.

## Phase 4: paper execution and risk

The paper subsystem will implement the same internal event semantics required for a later broker connector. It will simulate accepted, rejected, pending, partial and complete orders, cancellation and multi-leg recovery. Risk controls will be a deterministic service that evaluates known, authoritative inputs: active session, instrument status, price freshness, lot/tick constraints, exposure, limits and available simulated margin.

LLM-based research may draft a non-executable proposal with cited evidence. It cannot create, override or approve a risk decision. Any paper execution must still be traceable to a reviewed proposal and a policy decision.

## Phase 5: operations and security

The platform’s paper-pilot environment will add role-based access, secret isolation, audit logs, alerting, error budgets, monitoring and operating procedures. It will also establish data retention, privacy and provider-sharing policies for research/LLM workloads.

Live execution remains disabled at the end of this phase.

## Phase 6: controlled live-pilot preparation

This is not automatically scheduled. It begins only after separate approval for the selected broker, data providers, security model, compliance obligations and incident response. The live connector must use official authorization architecture, encrypted credentials, scoped permissions, idempotent order submission, broker/exchange reconciliation, human approval for activation, native protective orders where available and a tested kill switch.

## Workstreams and ownership decisions

| Workstream | Build from scratch | Reuse as reference only | Must be independently approved |
|---|---|---|---|
| Canonical domain/event model | Yes | Broker-neutral and trade-plan patterns from research | Schema changes after Phase 1 |
| Data/instrument pipeline | Yes | Adapter/fallback concepts | Data rights, vendor and retention policy |
| Backtest/research engine | Yes | Indicator and strategy examples | Dataset basis and research-promotion rules |
| Risk engine | Yes | Deterministic gate and risk-limit vocabulary | Risk-policy values and override process |
| Paper simulation | Yes | Paper/live UX and interface patterns | Scenario library and simulation fidelity |
| Live broker integration | No work until Phase 6 | Existing adapters only as research input | Broker, security, legal/compliance and pilot sign-off |
| LLM assistance | Yes, behind evidence boundaries | Typed multi-agent/research hand-off | Provider/security/data-sharing policy |

## Immediate next task after the first commit

Create an Architecture Decision Record set that freezes the Phase 1 canonical event model, India-market session/instrument boundary and paper-only execution policy. This work must include tests that demonstrate an order intent cannot mutate a position or P&L until a fill event is recorded.

## Non-negotiable controls

The project shall maintain paper-only default behaviour, no execution authority for LLMs, no live credentials in code or tests, deterministic risk decisions, source/freshness metadata for material market inputs, event-derived positions and P&L, per-leg state management for multi-leg strategies, human/policy approval for any transition to a live pilot, and explicit treatment of India-specific session/contract mechanics.

This is research and analysis only, not personalized financial advice.
