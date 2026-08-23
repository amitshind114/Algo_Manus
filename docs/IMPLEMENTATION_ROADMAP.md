# Implementation Roadmap

## Status

This roadmap replaces neither the existing master delivery plan nor its live-readiness gate. It turns the supplied specification into **small, test-first implementation slices**. Phase 0 is the only phase completed by the accompanying documentation; all following phases require review and approval before work begins.

| Status key | Meaning |
|---|---|
| **Complete** | Documentation or code has been accepted and validated. |
| **Proposed** | Defined for review; not started. |
| **Gated** | May not begin until named external approval/evidence exists. |

## Phase 0 — Audit and target plan

**Status:** Complete for review.

| Deliverable | Outcome |
|---|---|
| Architecture gap assessment | Exact retained foundation, material gaps, safety invariants and external gates. |
| Target architecture | Module boundaries, target contracts, mode model and execution flow. |
| UI/UX specification | Professional local terminal information architecture and state requirements. |
| Baseline validation | `make lint && make test` passed with 22 deterministic tests on 23 August 2026. |

**Exit decision:** approve Phase 1 only if the contract-first sequence is accepted.

## Phase 1 — Stabilize domain contracts and strategy registry

**Status:** Proposed.

| Work package | Scope | Explicitly excluded |
|---|---|---|
| Derivative-ready instruments | Extend identity with exchange/segment/type, expiry, strike, option type, lot size and tick size; add validation. | Live provider/download or synthetic options chain. |
| Strategy registry | Metadata, parameter schema, `StrategyContext`, registration port and SMA migration. | Multiple unvalidated strategies or direct order methods. |
| Execution vocabulary | Stable intent/order/fill/lifecycle/reconciliation event contracts and repository ports. | Broker gateway/SDK implementation. |
| Tests | Contract, regression and template tests. | Any change that weakens existing fixture tests. |

**Exit evidence:** all existing tests remain green; an unregistered strategy, unsupported interval and invalid parameter set fail explicitly; no strategy has database/network/order access.

## Phase 2 — Reproducible research and data lineage

**Status:** Proposed.

| Work package | Scope | Explicitly excluded |
|---|---|---|
| Dataset manifest and quality | Checksum, provider identity, retrieval/source times, interval/range, freshness, gaps, duplicate/OHLC validation and policy outcome. | Real provider adapter. |
| Backtest manifest | Git SHA when available, strategy version, parameters, data/instrument snapshot, engine version and cost assumptions. | Silent alteration of existing backtest economics. |
| Portfolio runner | Cash allocation, sizing constraints, multi-symbol event stream and standard metrics. | Claims of profitability or strategy recommendation. |
| Analysis artifacts | Equity/drawdown curves, trade ledger, rejected events, metric definition reference and immutable comparisons. | Dashboard-computed KPI shortcuts. |

**Exit evidence:** an experiment can be re-run from a manifest; missing/invalid lineage quarantines or rejects a run; basic metrics preserve backwards-compatible values where assumptions are unchanged.

## Phase 3 — Central risk, paper portfolio and lifecycle

**Status:** Proposed.

| Work package | Scope | Explicitly excluded |
|---|---|---|
| Risk engine | Versioned policies, quantity/notional/exposure/order-count/loss/drawdown/active-instrument/freshness/session/idempotency checks. | Live activation or policy override by UI. |
| Event ledger/projections | Durable order, fill, position, cash and P&L projections from immutable events. | Mutable order history. |
| Paper gateway | Full lifecycle state machine, simulated partial/rejected/cancelled scenarios and reconciliation protocol. | Broker connection, account access or real orders. |
| Tests | Failure injection, replay/restart, duplicate, stale data, market closed and kill-switch coverage. | Untested happy-path-only simulation. |

**Exit evidence:** an accepted paper intent follows risk policy into a replayable lifecycle; a risk failure cannot reach paper submission; position/P&L depends only on fill/reconciliation events.

## Phase 4 — Operations and local terminal hardening

**Status:** Proposed.

| Work package | Scope | Explicitly excluded |
|---|---|---|
| Storage operations | Migration versioning, backup/export/restore, path configuration and Windows-safe lifecycle. | Destructive migration without backup/recovery test. |
| Operations read models | Health, data freshness, provider status, last success/failure, active mode, kill switch and audit views. | Display of credentials or raw secrets. |
| Terminal refactor | Reusable Streamlit modules mapped to approved application query services, dark-first/light option and intentional empty/error/stale states. | UI-side business calculations or direct persistence. |
| Security checks | `.env.example`, ignore controls, CI-friendly secret scan/lint/test guidance and audit redaction tests. | Secret storage in client/UI state. |

**Exit evidence:** local Windows clone can create an environment, run all checks, start the terminal, backup/restore test data, inspect source/mode/risk/audit state and remain paper-only.

## Phase 5 — Broker-ready interfaces and test doubles

**Status:** Proposed; **no production connector authorization.**

| Work package | Scope | Explicitly excluded |
|---|---|---|
| Adapter contracts | Provider/broker gateways, configuration validation, error translation, rate-limit/retry/timeout policies and mock adapters. | API authentication, token generation, data download, account calls or order placement. |
| Integration tests | Contract fixtures for master/data/order/reconciliation responses; secrets safety checks. | Vendor SDK execution. |
| Readiness evidence | Provider selection record, official API/terms review, source rights, security design and paper/reconciliation evidence. | Enabling a real adapter. |

**Exit evidence:** mock adapter suite proves the ports; decision record names the remaining external approvals.

## Phase 6 — Controlled provider/paper and eventual live-pilot gate

**Status:** Gated; not authorized.

This phase requires separate approval after the preceding phases are demonstrated. It must not be inferred from this roadmap. The required evidence includes official provider terms/capabilities, data-rights review, credential isolation, monitoring/recovery, reconciliation, rate limits, paper tests, risk policy approval and a human-owned incident/kill process. Any production broker implementation begins in a constrained paper/sandbox context and does not authorize live orders.

## Delivery discipline for every approved phase

| Control | Required evidence |
|---|---|
| Source change | Small commit with no generated clutter, no secret and no silent behavior change. |
| Test change | New business/failure case covered before or together with implementation; prior suite still passes. |
| Documentation | README/relevant operational docs updated with run and validation instructions. |
| UI change | Service-backed values only; visible mode/data/timestamp/unit and intentional empty/error/stale state. |
| Safety | No broker, account, market-data, cloud or live activation unless the phase explicitly carries the separate authorization. |

## Proposed next ticket

**Phase 1A: Strategy registry and metadata contracts.** This is the smallest high-leverage next step: it preserves the proven SMA path, supports a schema-driven Strategy Lab later, and adds no external-market or execution exposure.

## References

[1]: ./ARCHITECTURE_GAP_ASSESSMENT.md "Architecture gap assessment"
[2]: ./TARGET_ARCHITECTURE.md "Target architecture"
[3]: ./MASTER_DELIVERY_PLAN.md "Existing master delivery plan"
