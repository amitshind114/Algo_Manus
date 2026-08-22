# Master Delivery Plan: Research to Controlled Deployment

## Delivery objective

This plan defines the end-to-end build sequence for **India Algo Platform**: an India-first research, backtesting, paper-trading and future controlled-execution platform for NSE/BSE cash equities and NFO listed derivatives. It begins with governance and canonical data/event models, progresses through reproducible research and paper execution, and ends with deployment operations. 

> **Live execution is a gated future capability, not a default outcome of the roadmap.** Phases 1–8 can deliver a valuable research and paper-trading product. Phase 9 starts only after independent legal, broker, data-rights, security and operational approval.

## Success definition

The target outcome is not a collection of trading strategies or a broker-login screen. It is a system that can explain every research result, risk decision, paper order and eventual live order using durable evidence. A market observation must have a source and freshness record; a strategy result must have a reproducible experiment specification; a position and P&L figure must derive from reconciled events; and a future execution request must pass independent, deterministic policy checks.

## Ten-phase program

| Phase | Theme | Primary outcome | Main exit gate |
|---:|---|---|---|
| 1 | Governance and engineering foundation | A controlled repository, explicit scope, quality rules and approval model | Paper-only policy and architecture decisions accepted |
| 2 | Canonical domain and event contracts | Shared typed vocabulary for India markets, research, orders, fills and risk | Contract test suite proves order intent cannot mutate position/P&L |
| 3 | Instrument, calendar and data-lineage platform | Versioned India-market instruments, sessions, data-source and freshness evidence | Every material research input is traceable and session-aware |
| 4 | Research and backtesting engine | Reproducible experiments with realistic assumptions and promotion gates | Backtests run from approved point-in-time datasets with full lineage |
| 5 | Portfolio analytics and deterministic risk | Exposure, P&L, limits and pre-trade policies from authoritative state | Risk decisions are deterministic, auditable and fail closed on bad inputs |
| 6 | Paper execution and reconciliation | Event-driven simulation with partial fills, rejects and multi-leg state | Paper orders reconcile through complete lifecycle and recovery scenarios |
| 7 | Research and operations interfaces | Governed user workflows and evidence-bound AI assistance | All user actions are role-scoped, auditable and non-executable by default |
| 8 | Security, observability and release operations | A reliable paper-pilot environment with monitoring and recovery controls | Security/reliability acceptance review passes for paper operations |
| 9 | Controlled live-pilot readiness | A separately approved, broker-specific live execution boundary | Compliance, broker, data, security and incident readiness are signed off |
| 10 | Deployment, handover and continuous controls | Progressive rollout, rollback, operating playbooks and ownership transfer | Approved production release and post-launch control cycle are active |

---

## Phase 1 — Governance and engineering foundation

### Objective

Turn the current documentation repository into a controlled engineering program. This phase establishes scope, decision rights, contribution standards, architecture decision records, test/quality expectations, release conventions and an explicit paper-only boundary.

### Deliverables

| Area | Deliverable |
|---|---|
| Product governance | Product requirements document, non-goals, user roles, success measures and decision log |
| Architecture governance | Architecture Decision Record template and initial decisions for paper-only policy, event model ownership, data lineage and AI separation |
| Engineering standards | Language/runtime selection, formatting/linting policy, test pyramid, dependency policy, secret-handling rule and branch/review convention |
| Repository controls | Licence decision, `CONTRIBUTING.md`, code ownership/review model, issue/PR templates and CI quality baseline |
| Delivery controls | Environment classification, release criteria and a change-management procedure |

### Exit gate

The owner accepts the paper-only first-release boundary; repository conventions and quality gates are executable in CI; no code path can include broker credentials, a live order endpoint or an execution bypass.

---

## Phase 2 — Canonical domain and event contracts

### Objective

Build the shared vocabulary that every future service uses. Domain types must express India-specific assets and sessions without embedding exchange/broker rules in strategies or UI code.

### Deliverables

| Domain group | Core contracts |
|---|---|
| Markets | Venue, exchange segment, market session, holiday, underlying, cash equity, future, option, expiry, lot size, tick size and trading symbol |
| Data | Observation, quote, OHLCV bar, option-chain snapshot, source, retrieval time, freshness, adjustment basis and schema version |
| Research | Strategy specification, parameter set, hypothesis, universe, information cutoff, experiment run, execution assumptions and evidence reference |
| Portfolio | Account scope, cash, holding, position, exposure, realised/unrealised P&L and valuation snapshot |
| Execution | Proposal, policy request, policy decision, order intent, broker submission, acknowledgement, exchange state, fill, cancellation, rejection and reconciliation correction |
| Governance | Correlation ID, causation ID, event time, received time, actor, approval and audit record |

### Required tests

The contract suite must demonstrate that an order intent is distinct from a fill; a rejected, cancelled or pending order does not change positions; partial fills change position by the fill quantity only; and a correction creates a new immutable event instead of rewriting history.

### Exit gate

All services can depend on a versioned domain package. The India-market examples cover cash equity and NFO multi-leg derivatives, while future FX/crypto extensions remain explicit separate modules.

---

## Phase 3 — India-market instruments, calendars and data lineage

### Objective

Build authoritative, versioned handling for India-market instruments and all research inputs. Data quality and provenance must be visible rather than inferred from a fallback path.

### Deliverables

| Capability | Required behaviour |
|---|---|
| Instrument master | Versioned security/contract identities, listings, expiry, lot/tick rules, strike metadata and symbol mappings |
| Calendar service | NSE/BSE/NFO sessions, holidays, expiries, special sessions and market-status API |
| Source registry | Provider/source classification, usage-right record, supported fields, freshness policy and approved use cases |
| Data lineage | Source URL/identifier, retrieval time, source timestamp, request parameters, adjustment basis, checksum/schema and cache age |
| Quality controls | Completeness, staleness, duplicate, outlier, session, symbol-mapping and contract-validity checks |
| Storage policy | Raw/normalized/curated layers, retention rules and replayable data version references |

### Backtest requirement

Research datasets must support point-in-time reconstruction. A backtest may not use data that would not have been known at the evaluation timestamp. The experiment should fail or be visibly quarantined when lineage or freshness is insufficient.

### Exit gate

Every material research bar, quote, contract and event calendar record has an explicit provenance and version. An unapproved fallback source cannot silently supply live-risk or execution inputs.

---

## Phase 4 — Reproducible research and backtesting engine

### Objective

Create a research platform where strategies are versioned hypotheses and results are reproducible experiments—not marketing metrics.

### Deliverables

| Research component | Required design |
|---|---|
| Strategy SDK | Typed signals, parameters, universe, session rule, entry/exit condition and sizing interface |
| Experiment specification | Strategy version, data version, information cutoff, time window, rebalance/session policy and random seed when applicable |
| Execution assumptions | Bid/ask or spread model, slippage, brokerage, statutory costs/taxes, market-impact interface, order type and partial-fill assumptions |
| Validation workflow | Train/validation/test split, embargo/censor gap, walk-forward test, sensitivity tests and failure-case analysis |
| Result registry | Immutable experiment ID, metrics, artifacts, charts, trades/events, source data references and review status |
| Promotion gate | Research-only, paper-eligible and rejected states with independent review evidence |

### India-market emphasis

Equity and F&O experiments must account for cash-equity versus derivative sessions, expiry/roll rules, lot/tick sizes, corporate actions, contract availability, liquidity limitations and cost treatment. Option simulations cannot be promoted using only theoretical premiums or hard-coded expiry assumptions.

### Exit gate

At least one reference strategy executes against an approved fixture/dataset with reproducible results and a complete assumptions report. A result cannot be marked paper-eligible without passing quality, robustness and evidence gates.

---

## Phase 5 — Portfolio analytics and deterministic risk controls

### Objective

Implement the policies that protect the paper portfolio now and provide the future live boundary later. Risk controls must run independently of research narratives, UI choices and LLM output.

### Deliverables

| Control plane | Required capability |
|---|---|
| Portfolio valuation | Event-derived cash, holdings, positions, realised/unrealised P&L and valuation timestamp |
| Exposure analysis | Symbol, sector, underlying, delta/option exposure, concentration and scenario aggregation interfaces |
| Limits policy | Per-order, per-symbol, per-strategy, daily loss, daily turnover, gross/net exposure, margin and session limits |
| Pre-trade policy | Market-open, data-freshness, instrument-validity, lot/tick, proposal state, exposure, margin and multi-leg checks |
| Kill controls | Paper shutdown, strategy disablement, risk freeze and audit-recorded override process |
| Reporting | Explainable allow/reduce/defer/reject outcomes with exact inputs and policy version |

### Exit gate

Given the same authoritative state and policy version, the risk service returns the same outcome. Missing/stale/ambiguous inputs cause a visible defer or reject state, not a permissive default.

---

## Phase 6 — Paper execution and reconciliation

### Objective

Build an execution simulator that is operationally useful rather than a simple “instant fill” calculator. The simulator must exercise the same event interfaces and failure patterns expected from a future broker integration.

### Deliverables

| Paper-execution component | Required behaviour |
|---|---|
| Order state machine | Intent, submitted, accepted, working, partially filled, filled, rejected, cancelled, expired and reconciled states |
| Fill simulator | Configurable bid/ask, slippage, queue/latency, partial fill, price-limit and session assumptions |
| Multi-leg orchestration | Parent/leg relationships, precondition check, staged submission, incomplete-leg handling, cancellation and contingency policy |
| Protection simulation | Stop/target/trailing protection representation with monitoring and state reconciliation |
| Reconciliation | Compare expected simulation events with venue-style reports; produce corrections without destructive rewrites |
| Scenario library | Market closed, stale data, rejected margin, partial hedge, delayed cancel, duplicate request and system-restart recovery tests |

### Exit gate

The paper environment supports a complete order-to-P&L narrative from immutable events. Multi-leg tests demonstrate safe recovery from partial, rejected and delayed states.

---

## Phase 7 — Research and operations interfaces with governed AI assistance

### Objective

Create workflows that help users research, review, simulate and operate the system without giving any display or AI component implicit execution authority.

### Deliverables

| Interface | Required behaviour |
|---|---|
| Research workspace | Evidence-linked datasets, strategy specifications, experiments, results, validation status and review comments |
| Paper-trading console | Proposal review, policy decision, paper-order state, fills, positions, alerts and reconciliation timeline |
| Risk/operations dashboard | Limits, exposure, data freshness, policy blocks, failed jobs, audit trail and kill-switch status |
| AI research assistant | Source-cited summarization, gap detection and non-executable proposal drafting only |
| Access control | Role-scoped view/edit/approve capabilities; no shared accounts or hidden privilege escalation |

### AI control rules

AI assistance must not store or receive execution credentials, write an approval, override a risk block, invent a market-data fact or create a live order. Prompts, model/version, cited evidence and response metadata should be retained according to the project’s data policy.

### Exit gate

All key user paths are auditable. A user can understand why a proposal was blocked, what data it used and which policy/evidence state applied.

---

## Phase 8 — Security, observability, testing and release operations

### Objective

Make the paper-pilot environment trustworthy enough to operate repeatedly. Reliability and security are not deferred to a live-launch week.

### Deliverables

| Discipline | Required capability |
|---|---|
| Identity and secrets | Role-based access, least privilege, encrypted secret storage, rotation procedure and no secrets in logs/tests/client code |
| Application security | Threat model, dependency scanning, secure configuration, input validation, rate limits and audit integrity |
| Test strategy | Unit, contract, integration, end-to-end, replay, property, failure-injection and regression test suites |
| Observability | Structured logs, metrics, traces, health checks, data freshness monitors, policy decision monitoring and alert routing |
| Operations | Runbooks, incident severity, rollback procedures, backup/restore tests, change management and release checklist |
| Delivery pipeline | Reproducible builds, signed/versioned artifacts, CI quality gates, environment promotion and deployment review |

### Exit gate

A paper-pilot acceptance review confirms that security boundaries, test coverage, monitoring, incident response and rollback procedures are operationally demonstrated.

---

## Phase 9 — Controlled live-pilot readiness

### Objective

Prepare a broker-specific live boundary only if it has separate approval. The goal is a small, controlled pilot with policy enforcement, not broad automation.

### Preconditions

| Approval area | Evidence required before implementation or activation |
|---|---|
| Legal/compliance | Applicable regulatory, exchange, broker and data-rights requirements have been reviewed for the intended activity and jurisdiction |
| Broker/venue | Official API agreement, supported order/instrument capabilities, authentication architecture, rate limits and reconciliation interfaces are understood |
| Security | Threat model, credential isolation, approval model, audit retention and incident procedures are approved |
| Risk | Live policy values, limits, overrides, kill switch and escalation ownership are approved |
| Operations | Monitoring, on-call, rollout/rollback, EOD reconciliation and business-continuity procedures are tested |

### Live-pilot deliverables

The implementation should use official broker authorization flows, encrypted scoped credentials, idempotent submission, broker/order/trade postback or polling reconciliation, native protective orders where supported, explicit human activation, fixed pilot limits and immediate kill capability. Paper/live code must share canonical event contracts but have separate credentials, accounts, mode labels and authorization policies.

### Exit gate

The pilot can activate only after all preconditions are signed off and the system passes dry-run/reconciliation and incident scenarios. Any missing evidence returns the platform to paper-only mode.

---

## Phase 10 — Deployment, handover and continuous controls

### Objective

Deploy only approved services through progressive rollout and establish a sustainable operating model.

### Deliverables

| Area | Required outcome |
|---|---|
| Deployment | Environment-specific infrastructure, configuration promotion, deployment records, feature flags and rollback automation |
| Release strategy | Paper/staging verification, limited pilot cohort/account scope, controlled expansion criteria and freeze policy |
| Reconciliation operations | Intraday and end-of-day data/order/trade/position/P&L reconciliation with exception workflow |
| Governance | Periodic risk-policy review, model/strategy review, data-provider review, access review and change approval |
| Handover | Architecture guide, service ownership, runbooks, disaster recovery exercises, onboarding and known-risk register |
| Continuous improvement | Post-incident review, experiment review, backlog governance and evidence-based phase expansion |

### Exit gate

An approved deployment has named service owners, monitored service-level objectives, tested rollback/recovery, operating documentation and a continuing review cadence. Deployment completion does not remove the paper-only fallback or risk-kill controls.

## Cross-phase quality gates

| Gate | Applies from | Requirement |
|---|---:|---|
| No silent fallback | 3 | Any degraded data or unavailable policy input is labelled, quarantined or rejected according to approved policy |
| Evidence lineage | 3 | Research, data and event results retain source/version/time references |
| Reproducibility | 4 | Experiment results can be rerun from stored specifications and approved datasets |
| Deterministic risk | 5 | Policy results are independent of LLM/UI narrative and are fully auditable |
| Event-derived state | 6 | Position/P&L/risk state derives from reconciled events, not submitted-order records |
| Least privilege | 7 | UI, AI, data and future execution boundaries have distinct permissions and secrets |
| Release readiness | 8 | Tests, monitoring, backup/restore and incident/rollback procedures are demonstrated |
| Explicit live authorization | 9 | No live capability activates absent independent documented approval |

## Immediate continuation point

The next implementation session begins with **Phase 1**. The first build ticket should establish the repository’s licence decision, contribution standards, Architecture Decision Record format, domain-package technology choice and CI checks. No broker integration, live market-data call, deployment or execution feature is part of that first ticket.

This is research and analysis only, not personalized financial advice.
