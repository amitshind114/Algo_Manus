# Architecture Gap Assessment

## Status and decision

**Status:** Phase 0 assessment for review; no broad implementation is authorized by this document.

Algo Manus is a credible **local, fixture-backed research and paper-operations foundation**, rather than a completed broker-ready trading platform. It already establishes several high-value safeguards: immutable instrument snapshots, source-aware candle contracts, reproducible SMA experiment specifications, next-bar fills, a deterministic paper-risk decision, append-only ledger events, audit redaction, and a service-backed Streamlit workbench. The current baseline passed `make lint && make test` with **22 deterministic tests** on 23 August 2026.

The supplied specification is directionally aligned with the repository’s existing master plan. The required work is a controlled expansion of the current foundation—not a replacement of it and not a UI-only rewrite. The key architectural decision is to evolve every layer around **immutable evidence, explicit ports, deterministic policy, and event-derived state**. The existing Master Delivery Plan already establishes those invariants and keeps live execution as a separately approved future gate.[1]

> **Phase 0 recommendation:** retain the existing domain/application/infrastructure separation, preserve the fixture mode as a clearly labelled demonstration path, and first build missing contracts and regression tests. Do not introduce broker credentials, provider calls, live market feeds, background runners, cloud deployment, or live order placement.

## Evidence reviewed

| Evidence | Current finding | Consequence for the target build |
|---|---|---|
| `src/algo_manus/domain/strategy.py` | A pure `Strategy` protocol and immutable parameter revision exist, but only expose `strategy_id`, history requirement and signal generation. | Extend rather than replace the contract with metadata, schema validation, versioning, context and registry ports.[2] |
| `src/algo_manus/application/backtesting.py` | Next-bar-open long-only backtests avoid a direct look-ahead fill; lineage and cost/slippage inputs already exist. | Retain this correctness baseline while adding portfolio allocation, execution assumptions and richer metrics. |
| `src/algo_manus/application/paper_execution.py` and `domain/risk.py` | Paper submission is risk-gated and auditable, but policy coverage and lifecycle state are deliberately narrow. | Split reusable policy evaluation, portfolio state and execution lifecycle into explicit services before broker adapters. |
| `src/algo_manus/ui/workbench.py` | Fixed sidebar navigation, search, multi-security testing, KPI comparison, reporting and fixture paper-event pages are functional. | Refactor into reusable view modules only after contracts exist; never use UI state as the system of record.[3] |
| `src/algo_manus/application/demo_workbench.py` | The demonstration calls production application services, but uses synthetic fixture bars, a memory experiment repository and session-local history. | Preserve the clear fixture lab; add persistent research/paper views backed by repositories later, without presenting fixture outputs as market evidence.[4] |
| `docs/MASTER_DELIVERY_PLAN.md` | Ten-phase end-state already covers data lineage, research, risk, paper reconciliation, interfaces, security and a controlled live gate. | Consolidate the newly supplied requirements into a more executable Phase 0–5 plan instead of creating a competing architecture.[1] |

## Current capability map

| Capability area | Current state | Assessment |
|---|---|---|
| Local developer baseline | Python package, Make targets, deterministic tests and Windows SQLite cleanup coverage are present. | **Retain and extend.** |
| Instrument master | Canonical identity, immutable snapshot, cache/reconciliation abstraction and availability checks exist for fixture/offline flow. | **Extend.** Derivatives attributes, expiry/chain resolvers, data freshness and broker-owned source integration remain unavailable. |
| Market data | Candle dataset and provenance contracts enforce permitted use cases; non-broker data is rejected in paper/risk contexts. | **Extend.** Provider ports, comprehensive validation, cache metadata and real adapters are missing by design. |
| Strategy system | SMA crossover plus immutable parameter revisions are tested. | **Major gap.** No registry, metadata, discovery, context, parameter schema or template suite. |
| Backtesting | Multi-security experiment batching, next-bar fills, commission/slippage and a basic leaderboard work in local fixtures. | **Major gap.** No portfolio cash allocator, standard metric suite, rejected/partial fills, spread model, walk-forward or persisted artifacts. |
| Experiment reproducibility | Strategy revision, data set IDs and backtest specification identity are retained. | **Extend.** Add engine version, Git SHA, timestamp policy, time window, checksum, review state and immutable artifacts. |
| Risk | Deterministic paper policy gates kill switch, order count, daily realised loss, long-only rule, per-symbol/gross notional and cash. | **Major gap.** Need a central risk engine, policy versioning, idempotency, active instrument, market-session, data freshness and drawdown controls. |
| Paper execution | Risk decision and accepted/rejected/fill events are appended locally. | **Major gap.** Needs full lifecycle, positions/P&L ledger, persistence, reconciliation and recovery scenarios. |
| UI and operations | Functional fixture workbench, visual fixture banner, simple KPI/reporting pages, audit redaction and health projection exist. | **Extend.** No persisted operations view, orders/audit browser, settings, light option, system-health history, backup flow or intentional loading/error states. |
| Broker/live readiness | Abstract master-sync interfaces only; no credentials, SDKs, calls, runner or deployment. | **Correctly blocked.** Keep blocked until paper/reconciliation, security, data-rights and explicit approval evidence are complete. |

## Gap priorities and remediation sequence

| Priority | Gap | Why it is material | First safe remediation | Acceptance evidence |
|---:|---|---|---|---|
| P0 | Shared domain vocabulary is incomplete for derivatives, portfolio, full order lifecycle and reconciliation. | Later services would otherwise invent incompatible types. | Add type-only domain entities, enums and repository ports with contract tests. | No service can mutate positions from an intent or rejected order. |
| P0 | Strategy contract has no registry or metadata model. | Strategy configuration and reproducibility cannot scale beyond a one-off SMA implementation. | Introduce a registry port, metadata, parameter schema and `StrategyContext`; retain SMA as the reference plug-in. | New strategy template tests cover validation, determinism and declared support. |
| P0 | Fixture workbench state is session/memory based. | It cannot truthfully show persisted research or paper history. | Introduce read/query use cases over existing SQLite repositories; leave fixture mode isolated. | Restart-safe history can be viewed without UI-side calculations. |
| P1 | Backtest engine lacks portfolio and realistic execution controls. | Single-symbol results can be misread as portfolio performance. | Add immutable run manifest and portfolio allocation interface before metrics expansion. | Repeat run from manifest produces the same result and assumption report. |
| P1 | Risk policy is not an independent engine with authoritative state. | No future execution path may trust UI/session state. | Define `RiskEngine`, risk-policy repository and portfolio projection interfaces. | Missing/stale/invalid inputs fail closed with recorded codes. |
| P1 | Paper lifecycle/ledger is incomplete. | An instant-fill simulator cannot validate operational failure paths. | Add state machine, order/fill/position repositories and replay projection. | Partial-fill, cancel, duplicate, restart and reconciliation scenarios pass. |
| P2 | Operations/security posture lacks migrations, backup/restore and hardened runbooks. | Paper use needs recovery evidence before it is relied upon. | Add storage versioning, non-destructive export/restore workflow and structured run correlation. | Backup/restore and recovery tests are repeatable on Windows. |
| P2 | UI navigation does not map to the complete operations model. | The current terminal cannot yet inspect persisted order, audit or health state. | Add reusable service-backed views only after query contracts are available. | Every screen has a visible mode/source/freshness/error state. |
| Gated | Real broker/data adapters and any runner. | They introduce credentials, rate limits, real-market data and execution risk. | Define isolated ports and test doubles only. | Separate approval plus official provider terms, credentials and paper/reconciliation evidence. |

## Non-negotiable invariants

The following rules apply to every future change.

| Invariant | Required interpretation |
|---|---|
| **UI has no execution authority** | Streamlit may invoke application use cases only. It must not call a database connection, broker SDK, strategy internals or execution adapter. |
| **Strategies create intent, never orders** | Strategy output is a signal or `OrderIntent`; only the application path can present it to the risk engine. |
| **Risk fails closed** | Unknown instrument validity, stale/missing marks, missing session, unavailable portfolio state or unapproved policy version returns a named defer/reject decision. |
| **State is event-derived** | A submitted order never changes position/P&L. Only immutable fill/reconciliation events update projections. |
| **Research is reproducible** | A run stores strategy version, parameter revision, engine version, data snapshot/checksum, cost model, time window and source policy. |
| **No silent data substitution** | Fixtures are labelled; a missing approved source cannot silently become a fallback. |
| **Live is default-denied** | No live code path, configuration or UI control becomes active without an independent documented readiness gate. |
| **Secrets never cross display/audit boundaries** | Credentials and tokens stay out of source, logs, UI, screenshot, test fixtures and commit history. |

## Deferred decisions and external gates

The Phase 0 deliverables deliberately do **not** decide a specific broker, provider, deployment environment or live-trading mode. Those choices change security, reliability, legal, data-rights and operating requirements; they require their own approval records. A future running service should be selected only after its expected latency, frequency, runtime dependencies, state durability and operational ownership are known.

| Deferred item | Current disposition | Evidence required before implementation or activation |
|---|---|---|
| Broker instrument-master and historical/live data integration | Not approved; no adapter or request may be added. | Official provider documentation/terms, source-right review, credential handling design, retry/rate-limit policy and test doubles. |
| Broker paper connectivity | Not approved; local simulator remains the only paper path. | Reconciliation design, risk/portfolio lifecycle tests and approved sandbox/paper account workflow. |
| Live execution | Explicitly unavailable. | Separate legal/compliance, broker, security, risk, operations and incident-readiness approvals.[1] |
| Cloud deployment/background runners | Not approved; local use is the only operating mode. | Workload/latency model, deployment/rollback runbook, monitoring, persistence and recovery evidence. |
| Derivative support | Model target only; no synthetic option universe or fabricated chain data. | Canonical contract metadata, expiry/calendar policy and approved provider/source integration. |

## Phase 0 exit criteria

Phase 0 is complete when the accompanying target architecture, roadmap and UI/UX specification are accepted, and the owner selects the first small implementation slice. The proposed first slice is **strategy registry and metadata contracts with tests**, because it improves the research workflow without requiring any external market, broker, cloud or execution capability.

## References

[1]: ./MASTER_DELIVERY_PLAN.md "Existing master delivery plan"
[2]: ../src/algo_manus/domain/strategy.py "Current strategy contract"
[3]: ../src/algo_manus/ui/workbench.py "Current local workbench"
[4]: ../src/algo_manus/application/demo_workbench.py "Fixture workbench orchestration"
