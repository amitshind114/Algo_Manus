# Adopted Production Blueprint — Algo Manus

## Decision

**Algo Manus is the primary system of record and the only codebase for future build work.** The end-to-end production blueprint adopted on 25 August 2026 governs architecture decisions, but delivery remains local-first and one approved vertical slice at a time. Eagle Base may remain a private reference, but it is not the implementation target and no code is copied into Algo Manus without a focused review, tests and an explicit approval.

> A visible screen is not evidence of an operating capability. Every research, paper and future live outcome must remain traceable to immutable source, policy and event evidence.

## Current foundation

Algo Manus is no longer a blank research shell. The current local implementation has the following proven foundation.

| Blueprint concern | Current Algo Manus capability | Remaining integration gap |
|---|---|---|
| Canonical instruments | Credential-free Angel public instrument master, typed canonical identities and immutable SQLite snapshots. | Exchange calendars, corporate actions, derivative contract rules, session calendars and NFO/MCX readiness. |
| Historical research data | Manual authenticated Angel candle ingestion, immutable SQLite datasets, source hashes and validation policy. | Local user configuration is required; no retained authenticated candle dataset has yet been used in the local UI. |
| Session boundary | Manual local Angel session acquisition with in-memory token handoff and display-safe readiness state. | Provider session expiry/refresh needs user-configured local values; no unattended session lifecycle exists. |
| Research evidence | Typed strategies, next-bar backtests, reproducible manifests, retained-dataset selection and source-aware dataset lineage. | Censor/embargo workflow, walk-forward evaluation, corporate-action policy and richer India-market cost treatment. |
| Deterministic risk | Central risk engine, persisted controls, kill-switch context and risk-decision evidence exist for paper operations. | A single canonical event spine must make risk decisions structurally unavoidable for all paper lifecycle transitions. |
| Paper operations | Local risk-gated paper submission, fill/cancel events, append-only ledger and audit/projection reads. | Canonical order lifecycle, partial fills, limit-order rules, reconciliation records and event-derived position/P&L must be integrated end to end. |
| User interface | Local Streamlit research workbench with explicit fixture labels, source status, session status and retained-dataset research controls. | Separate paper operations views sourced from the canonical ledger; real-time monitoring remains deferred. |
| Live capability | Explicitly unavailable. | Must remain unavailable until separate legal, broker, security, paper-evidence and operational approvals. |

The completed public-instrument, historical-data, local-session and retained-dataset work remains valuable. It forms the evidence base for the next operating slice; it must not be replaced by an untyped or UI-first rewrite.

## Non-negotiable architecture rules

1. **Research, UI and strategies do not call broker or execution paths directly.** A UI invokes application services only; strategies produce signals or proposals, never orders.
2. **Risk is fail-closed and structurally interposed.** An unavailable policy, stale data, invalid instrument or missing authoritative state returns a named deny/defer outcome.
3. **State is event-derived.** An intent, submission, acknowledgement, fill, cancellation and reconciliation outcome are distinct immutable events. Only fill/reconciliation evidence changes projected positions or P&L.
4. **Paper is honest.** Paper operations are labelled simulation and must use declared assumptions. Historical replay is research, not a claim of paper fill quality.
5. **Evidence is immutable and explicit.** Dataset identity, raw hash, source, retrieval time, validation outcome, strategy revision, policy version and execution assumptions are retained together.
6. **Fixtures never silently substitute broker data.** Fixture, retained broker and future live-source results remain visibly distinct.
7. **Live is default-denied.** No order, cancellation, account, position, market-price feed, WebSocket, scheduler, cloud runner or broker execution endpoint is added without a later separately approved capability gate.

## Delivery sequence: vertical slices, not disconnected layers

The broad production architecture is delivered through the following dependency-ordered slices. Each slice must finish tests, local UI evidence, documentation, a clean commit and a separate approval before the next one begins.

| Slice | Outcome | Existing foundation used | Explicitly excluded |
|---|---|---|---|
| **A–D — completed** | Immutable public master, manual historical research data, local session boundary and retained-dataset backtests. | Instruments, market-data, experiment, research-manifest and Streamlit layers. | Account state, orders, feeds, WebSockets, scheduling and live execution. |
| **E — next** | One canonical **paper event spine**: strategy proposal → risk decision → limit-order paper intent → accepted/rejected/working/partial/fill/cancel/reconciliation events → event-derived position/P&L projection. | Existing risk engine, execution contracts, paper ledger, SQLite evidence and audit views. | Broker calls, real account state, live prices, WebSockets and live orders. |
| **F** | Conservative paper limit-fill simulator and reconciliation scenarios, including partial fill, no-fill, duplicate request, cancellation and restart replay. | Slice E canonical event spine and retained research evidence. | Claims of queue-position realism without an approved order-book data basis. |
| **G** | Paper operations console and local monitoring views from immutable event/projection reads. | Event ledger, projections, risk decisions and audit records. | Unattended automation, external alerting or cloud deployment. |
| **H** | India-market domain expansion: calendar, corporate-action policy, NFO contract/expiry/lot/tick metadata, then MCX contract metadata. | Typed instrument master and source evidence policies. | Fabricated chains, synthetic contract universes or unsupported provider assumptions. |
| **I** | Written paper-run criteria, data-quality review, controlled local paper validation and reproducible reporting. | Slices E–H. | Live activation or a performance recommendation. |
| **J — later gated** | Live-pilot readiness review only. | All previous evidence, independent legal/broker/security/operations review. | Activation, unless separately approved after readiness evidence exists. |

## Next implementation slice: Option E — canonical paper event spine

Option E is the next proposed contained build. It will use **no new broker endpoint**. Its acceptance criteria are:

| Requirement | Evidence required |
|---|---|
| One typed proposal/intent contract enters the paper path. | Deterministic test proves UI and strategies cannot construct an accepted paper order directly. |
| The central risk decision is recorded before any accepted paper lifecycle event. | Event ordering test and risk-denial replay test. |
| Paper lifecycle uses canonical event types and valid transitions. | Contract tests for accepted, rejected, working, partial-fill, filled, cancelled and reconciled outcomes. |
| Positions and P&L are projections, not mutable order fields. | Replay test reproduces the same projection from retained immutable events. |
| Limit-order simulation assumptions are explicit. | The initial simulator rejects market-order assumptions and clearly records its limited fill model. |
| The UI reads application projections only. | UI safety scan shows no direct SQLite, broker, strategy-internal or execution-adapter access. |

## Compliance and operating assumptions

The project must treat the regulatory and broker-specific parts of the production blueprint as **verification gates**, not hard-coded universal truths. The February 2025 SEBI circular is `SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/0000013`; SEBI issued a separate September 2025 implementation-timeline circular, `SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/132`. Exact exchange, broker, order-type, registration, authentication, IP, audit-retention and deployment conditions must be verified against current official exchange/broker documentation before any live-readiness work.

The current local configuration is deliberately not a secrets vault, automated session service or compliance approval. It is a manual, display-safe research-session boundary. A production secret-store decision, unattended monitoring, alerting and persistent service architecture remain later design gates.

## Definition of success

Algo Manus succeeds when a user can inspect one selected dataset, strategy revision, risk decision, paper event sequence, reconciliation record and P&L projection as a coherent, immutable local evidence trail. It does **not** succeed merely because a dashboard displays metrics, a strategy backtest produces a positive return or a broker login exists.

## References

[1]: https://www.sebi.gov.in/legal/circulars/feb-2025/safer-participation-of-retail-investors-in-algorithmic-trading_91614.html "SEBI — Safer participation of retail investors in Algorithmic trading, 4 February 2025"
[2]: https://www.sebi.gov.in/legal/circulars/sep-2025/extension-of-timeline-for-implementation-of-sebi-circular-dated-february-04-2025-on-safer-participation-of-retail-investors-in-algorithmic-trading-_96979.html "SEBI — Extension of timeline, 30 September 2025"
