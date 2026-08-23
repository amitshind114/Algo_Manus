# Local Central-Risk Control Persistence

## Scope

Phase 3C persists versioned central risk policies and append-only global kill-switch changes in local SQLite. It supplies a typed `RiskControlSnapshot` that a local paper submission can use as its authoritative policy and kill-state evidence. It does not add a broker, account session, provider, scheduler, cloud service, background process or live execution path.

## Persisted records

| Record | Identity and behavior | Purpose |
|---|---|---|
| Central risk policy | Immutable `policy_version`; idempotent same-content writes; conflicting content under the same version fails. | Reproducible quantity, notional and open-position policy inputs. |
| Kill-switch change | Append-only `change_id`, active state, reason and timezone-aware timestamp. | Durable local control history. |
| Risk control snapshot | One persisted policy plus the latest recorded kill-switch change. | Exact control evidence passed to a local paper decision. |

The local repository uses schema metadata and bounded SQLite connections. It retains the existing project convention of closing connections in `finally`, which supports Windows file-handle cleanup after use.

## Snapshot precedence

When a `RiskControlSnapshot` is supplied to `PaperExecutionService.submit`, the snapshot’s policy and kill-switch state override the transient constructor policy and the transient UI/session boolean. The paper `RISK_DECISION` event records the persisted policy version/timestamp, kill-switch change ID and durable kill state alongside the central decision outcome.

This prevents a caller from replacing a known persisted active kill state merely by passing `False` as a local method argument. A missing policy or missing initial kill-switch record fails before a snapshot can be constructed.

## Current limitation

The Streamlit fixture workbench still uses its session-level fixture control context. The new persistent control service is the local backend foundation and is tested through the paper submission path, but connecting the workbench to an operator-managed local control store is a future UI/operations phase. Until then, the workbench remains a clearly labelled fixture simulator.

## Deferred controls

Policy approval workflow, user identity/authorization, encrypted multi-user storage, remote audit shipping, policy retirement, portfolio/outstanding-order projections, broker-authoritative marks, reconciliation and all real execution remain out of scope. A local persisted control record alone does not confer paper-market or live-market readiness.

## Validation

```bash
make lint
make test
```

The suite verifies restart-safe policy/kill-state recovery, immutable policy conflict rejection, and a paper submission that honors the persisted kill state over a conflicting transient boolean while retaining append-only evidence.

This is research and analysis only, not personalized financial advice.
