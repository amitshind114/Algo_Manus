# Eagle Base Architecture Review and Design Decision

## Scope and conclusion

This document records a **static-only** review of [`vikaspathe11/eagle-base`][1] at commit `c67acc740f4c86d843a1a463339e06e882c0a155`. No Streamlit application, test, backtest, broker login, market-data call, live order, paper order, background runner or application database was run for this review.

Eagle Base is a useful reference for a structured India-market research system. Its strongest ideas are a package-oriented domain model, broker abstraction, risk/paper portfolio boundary, strategy registry, walk-forward scaffolding and broad test intent. It is **not** a template to fork for an unattended live system: the UI duplicates core logic, broker data can silently fall back to yfinance, API/kill-switch wiring is incomplete, and runtime/deployment controls are not sufficiently fail-closed.[2] [3] [4]

> **Design decision:** Algo_Manus will adopt the *patterns* of a broker-neutral boundary, versioned strategy parameters, paper lifecycle and operational dashboard. It will not copy Eagle Base source directly. No root licence file was present in the inspected checkout, so direct source reuse requires an independently verified licence decision.[1]

## What is valuable to retain as a design pattern

| Eagle Base pattern | Static evidence | Algo_Manus decision |
|---|---|---|
| Broker-neutral contract | `BrokerBase` unifies session, account, orders, positions, candles and funds.[5] | Keep the adapter boundary, but split market-data and execution capabilities and require explicit broker event reconciliation. |
| Provider chain and cache layers | `DataManager` prioritizes Angel One, then falls back to yfinance after memory/disk caches.[6] | Keep cache and source-selection concepts; make provenance part of every returned value and prohibit unapproved fallback in paper/live risk or execution paths. |
| Strategy registry and parameter UI | Strategy registry exists; Streamlit lets a user select a strategy and edit displayed parameters.[2] | Keep versioned parameters, but every change becomes a draft/reviewed configuration linked to a backtest run; never mutate a deployed strategy directly from the dashboard. |
| Paper portfolio and persistence | The paper subsystem models books, checks risk, simulates fills, persists SQLite state and verifies integrity.[2] | Keep event lifecycle and integrity-check principles; implement a durable event ledger and failure state rather than continue after persistence errors. |
| Risk gate and live safety chain | Live executor documents enable flag, token validation, idempotency, circuit breaker, risk checks, limits, audit and periodic reconciliation.[7] | Keep the layered policy idea, but rebuild using authoritative data, durable idempotency, fill-derived state and server-enforced approvals. |
| Streamlit operations view | Dashboard exposes data/backtest/strategy and live-monitor controls.[3] | Use it as a product-flow reference only. The MVP preview separates read models from command APIs and clearly labels simulated state. |
| Broad tests | Repository contains tests for no-look-ahead, paper state, risk, kill guard, strategies and walk-forward behavior.[2] | Preserve the test categories and add integration, replay, failure-injection, security and deployment tests. |

## Broker data ingestion: the first implementation boundary

Eagle Base makes the useful architectural choice to put historical OHLCV behind `DataManager`, but its implementation has two production-critical limitations. The returned `DataFrame` does not carry a structured provider/source record even though a provider is logged, and the chain silently uses yfinance when the broker path is unavailable.[6] That is convenient for local research but unsafe when a user assumes that broker-quality data informed a paper order, risk decision or future live action.

Algo_Manus will start with a dedicated **Market Data Gateway**, separate from all order-execution credentials. Every data response must carry source identity, requested instrument/contract version, source timestamp, received timestamp, session state, freshness assessment, adjustment basis and cache lineage. The gateway may allow a clearly labelled public-data fallback for exploratory research. It must reject or quarantine such a fallback for paper execution, portfolio valuation, risk limits or future live execution unless that exact fallback has been explicitly approved.

| Data use case | MVP source policy | Required result metadata |
|---|---|---|
| Historical strategy research | Broker/certified source first; labelled research fallback permitted | Provider, retrieval time, dataset version, adjustment basis, symbol/contract mapping, quality checks |
| Intraday paper data | Approved broker/data feed only; no silent public fallback | Exchange/session, source timestamp, received time, freshness/latency, closed-bar status, contract version |
| Risk and portfolio valuation | Fail closed when authoritative data is unavailable or stale | Latest authoritative price, freshness rule, valuation timestamp and policy outcome |
| Future live execution | Broker-authoritative data and instrument master only | Broker account/segment, token mapping, price/market status, pre-trade evidence ID |

## Strategy parameters: from dashboard inputs to governed configurations

The Eagle Base UI displays a “Strategy Parameter Editor,” but the visible action presents a success message without a durable strategy-configuration or experiment lineage in the inspected path.[3] The associated dashboard performance values are hard-coded display data, not a linked experiment report.[3]

Algo_Manus will make parameter adjustment a controlled workflow:

1. A user creates a **parameter draft** attached to a named, versioned strategy.
2. The system validates type/range/relationship constraints, such as fast period being below slow period.
3. The draft becomes an immutable **backtest specification** with a data version, period, costs, slippage, information cutoff and session rules.
4. A result can be promoted only to **paper-eligible** after defined reproducibility and review checks.
5. A running paper strategy receives a new **deployment revision** only after pause/review/redeploy. A dashboard edit never alters an in-flight strategy.

## Kill switch: use a state machine, not only a dashboard button

Eagle Base has an important conceptual separation between stopping strategy signals, cancelling pending orders and flattening positions.[4] The server router requires `{"confirm": "CONFIRM"}` for those calls and has tests for the confirmation guard.[4] [8] However, the Streamlit calls visible in `ui/app.py` do not attach that JSON body; the UI-level text confirmation therefore does not match the server request contract and may result in a validation error rather than a kill action.[3] The router’s audit history is also an in-memory 200-event ring buffer, while fallback flattening relies on a best-effort yfinance price and local portfolio mutation.[4]

The Algo_Manus MVP will provide a **paper-only safety console** with three distinct commands, each server-enforced and durably audited:

| Command | Intent | MVP behavior | Future live-pilot requirement |
|---|---|---|---|
| Freeze entries | Block new proposals/orders without changing existing paper positions | Immediate policy-state transition; all new entry requests rejected | Role-restricted command, durable audit and broker-side validation |
| Cancel working orders | Cancel eligible open paper orders | State-machine cancellation with per-order success/failure result | Reconcile cancellation acknowledgement with broker/exchange status |
| Flatten positions | Close paper positions through the simulator | Explicit generated exit events with scenario/price-source label | Broker-native close requests, fill reconciliation, failure escalation and human confirmation |

The command protocol will require a fresh server-issued challenge or a two-step confirmation, appropriate role authorization, a correlation ID and durable audit event. A browser field alone is not a control. The UI must show *requested*, *accepted*, *in progress*, *reconciled*, and *failed* states rather than declaring success immediately.

## What Algo_Manus must improve beyond Eagle Base

| Concern | Eagle Base observation | Required Algo_Manus response |
|---|---|---|
| Source truth | UI makes direct yfinance calls and includes an alternate local backtest path.[3] | One backend research/data path; UI is a typed client with no alternate calculator. |
| API safety | Historical review found broker account routes outside the API-key-protected group and an empty-key local fail-open mode.[2] | Separate local and deployed modes; deployed services refuse startup with missing auth/secrets, and all account/control endpoints require identity/authorization. |
| State failure | Live runner/paper code retains soft error handling around persistence and data.[2] | Treat state-store or authoritative-data failure as `DEGRADED`; block new orders until a visible reconciliation succeeds. |
| Reconciliation | Executor compares internal and broker positions but mutates local state based on broker quantity.[7] | Append correction events; preserve original state, require review for mismatches, and derive positions/P&L from the reconciled ledger. |
| Kill control | UI/server confirmation mismatch, in-memory audit and best-effort fallback close.[3] [4] | Durable commands/events, role control, action-specific states and reconciliation. |
| Deployment | Python project/CI are present, but no container or declarative deployment assets were found in the inspected checkout.[1] [9] | Containerized services, environment profiles, migration discipline, secrets policy, health checks, observability and rollback plan. |
| Research claims | UI contains hard-coded strategy performance values without experimental provenance.[3] | All metrics reference a result ID and visible data/cost/parameter assumptions; no hard-coded performance display. |

## Local and cloud operating model

The application should support a local developer/paper mode and a managed deployed paper-pilot mode using the **same domain and event contracts**. The key difference is authority and operational robustness, not two divergent codebases.

| Option | When it fits | Trade-offs | Setup complexity |
|---|---|---|---|
| Local-first research workstation | Single developer, exploratory historical research and offline fixture-based tests | Lowest operating overhead; machine must remain available for any local worker; no cloud-service guarantees | Low |
| Managed web application with scheduled jobs | Dashboard, API, database and bounded recurring data/research jobs | Easier access and operations; suitable when the workload fits a managed application environment | Medium |
| Dedicated persistent server | Custom broker SDK/runtime, Docker, more resources, fixed networking or a long-lived data/reconciliation worker | Greater operational responsibility and infrastructure cost; justified only by concrete runtime/scale requirements | High |

The MVP should begin with a local developer/paper profile plus a container-friendly service boundary. The eventual hosting choice remains a deployment decision made after the actual broker SDK, data frequency, resource needs and operational requirements are defined.

## MVP architecture decision

The clickable reference is [`mvp-preview.html`](mvp-preview.html); the implementation blueprint is [`MVP_BLUEPRINT.md`](MVP_BLUEPRINT.md). The MVP contains no actual broker connector or order endpoint. It proves the product flow: **source-aware data → reproducible backtest specification → reviewed parameter revision → deterministic paper risk decision → paper event ledger → operations safety console**.

## References

[1]: https://github.com/vikaspathe11/eagle-base/tree/c67acc740f4c86d843a1a463339e06e882c0a155
[2]: https://github.com/vikaspathe11/eagle-base/blob/c67acc740f4c86d843a1a463339e06e882c0a155/README.md
[3]: https://github.com/vikaspathe11/eagle-base/blob/c67acc740f4c86d843a1a463339e06e882c0a155/ui/app.py
[4]: https://github.com/vikaspathe11/eagle-base/blob/c67acc740f4c86d843a1a463339e06e882c0a155/api/routers/live.py
[5]: https://github.com/vikaspathe11/eagle-base/blob/c67acc740f4c86d843a1a463339e06e882c0a155/brokers/base.py
[6]: https://github.com/vikaspathe11/eagle-base/blob/c67acc740f4c86d843a1a463339e06e882c0a155/data/manager.py
[7]: https://github.com/vikaspathe11/eagle-base/blob/c67acc740f4c86d843a1a463339e06e882c0a155/live/executor.py
[8]: https://github.com/vikaspathe11/eagle-base/blob/c67acc740f4c86d843a1a463339e06e882c0a155/tests/test_kill_guard.py
[9]: https://github.com/vikaspathe11/eagle-base/blob/c67acc740f4c86d843a1a463339e06e882c0a155/pyproject.toml

This is research and analysis only, not personalized financial advice.
