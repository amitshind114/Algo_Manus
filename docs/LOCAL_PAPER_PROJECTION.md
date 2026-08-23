# Durable Local Paper Operations

## Scope

Phase 4A persists local fixture paper events in SQLite and projects them by deterministic replay. It is a local operational model for testing the application workflow. It is not a broker order ledger, a paper-market venue, an account record, a reconciliation system or live trading capability.

## Local event lifecycle

The fixture workbench writes the following local-only sequence to `paper_ledger.sqlite3` in the configured local data directory:

| Event | Local meaning | Projection effect |
|---|---|---|
| `RISK_DECISION` | Recorded central and local policy evaluation. | No cash or position change. |
| `ORDER_SUBMITTED` | A local simulation proposal passed the available controls. | Derived order becomes submitted. |
| `ORDER_REJECTED` | A local simulation proposal was blocked. | Derived order becomes rejected; no cash or position change. |
| `ORDER_FILLED` | The local simulator explicitly applied its fixture fill price. | Derived cash, long-only position quantity, average entry price and realised P&L update. |

New submitted/rejected/filled events carry self-describing side, quantity and price context so a later local replay can derive state without recalculating strategy signals or creating events.

## Projection rules

The workbench uses an explicit **fixture starting cash of ₹100,000**. Replay processes the append-only ledger in its SQLite sequence order.

| Case | Local replay behavior |
|---|---|
| Buy fill | Cash decreases by `quantity × fixture fill price`; quantity and weighted average entry price increase. |
| Sell fill | Cash increases by `quantity × fixture fill price`; realised P&L is measured against the derived average entry price. |
| Sell larger than derived holding | The event is marked unprojectable rather than creating a short position. |
| Missing/malformed legacy event context | The event is retained but listed as unprojectable; it is not invented or repaired. |
| Restart | The durable SQLite ledger is re-read and deterministically replayed. |

The replayed cash, positions, realised P&L, order states and session-order count become the portfolio snapshot supplied to the next local fixture proposal. This makes the next local risk check use prior durable local events instead of an always-empty session snapshot.

## Workbench and storage

By default the fixture workbench stores controls and paper events under `~/.algo-manus/`. Set `ALGO_MANUS_DATA_DIR` before launching Streamlit to choose a different local directory.

> The displayed state is derived from **fixture prices and local simulated fills only**. It has no broker-authoritative marks, exchange order acknowledgement, account balance, corporate-action adjustment or reconciliation evidence.

## Deferred work

Market/session calendars, partial fills, cancellation state transitions, fill allocation, commissions after fill, external marks, broker reconciliation, durable position snapshots, cash transfers, multi-account support and any real execution gateway are deliberately deferred. Broker or live work remains a separate approval gate.

## Validation

```bash
make lint
make test
```

The regression suite covers durable event read/restart, replayed cash/position/realised P&L/order state and safe handling of malformed or legacy fill evidence.

This is research and analysis only, not personalized financial advice.
