# Phase 1 Foundation

## What is implemented in this phase

Phase 1 builds the first real code boundary for the local-first platform. It does not fetch broker data or require any credential. It defines canonical instrument-master contracts, an isolated broker provider port, immutable SQLite snapshot storage and safe universe selection from a validated snapshot.

The architecture starts with an offline fixture adapter because correctness must be testable without a broker network, login, user account or market session. A future Angel One adapter will implement the existing provider port and normalize the broker’s official instrument master into the same contracts.

## Package layout

```text
src/algo_manus/
├── domain/                 # Provider-independent Instrument, snapshot and universe contracts
├── application/            # Sync and selected-universe use cases
└── infrastructure/
    ├── config.py           # Local, secret-free Phase 1 settings
    └── instruments/        # Broker-master port and immutable SQLite repository
tests/                      # Network-free fixture tests
```

## Core guarantees

| Guarantee | Phase 1 behaviour |
|---|---|
| Broker authority | A future broker adapter owns downloading/normalizing its master; UI and strategies never guess symbols or tokens. |
| Historic traceability | SQLite stores immutable snapshots rather than overwriting instrument records. |
| Stale protection | A snapshot freshness policy determines when synchronization is required. |
| Stable selection | Research universes store broker-derived instrument identities and a snapshot ID. |
| Invalid instrument handling | Unknown or inactive instruments cannot enter a newly created research universe; later snapshot checks flag missing, inactive or changed mappings for review. |
| Safe development | Tests use deterministic in-process fixtures and make no network, broker, data-provider or execution call. |

## Local checks

Run these commands from the repository root using Python 3.12:

```bash
make lint
make test
```

The optional `dev` dependency group adds pytest and Ruff for richer local workflows, but Phase 1's core tests rely on the Python standard library and can run without external packages.

## Explicitly deferred

The following are intentionally not implemented in Phase 1: the Angel One SDK adapter, credentials/TOTP, any network sync, historical bars, backtesting, Streamlit, paper orders, live orders, options execution and cloud deployment. These arrive only after the domain and snapshot foundation has been independently reviewed.

This is research and analysis only, not personalized financial advice.
