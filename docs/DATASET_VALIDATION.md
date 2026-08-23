# Deterministic Local Research-Dataset Validation

## Scope

Phase 2E introduces the first explicit local research-data quality decision before a multi-security experiment is allowed to create a manifest or run a backtest. It is a deterministic policy over the normalized local `CandleDataset`; it does not fetch data, verify a real exchange feed, repair a dataset or establish real-market completeness.

## Policy outcomes

| Outcome | Meaning | Experiment behavior |
|---|---|---|
| `ACCEPTED` | All supported local policy checks passed. | The dataset may be included in a research manifest and backtest. |
| `QUARANTINED` | The policy found a non-fatal condition requiring review. | The batch is blocked before backtesting; no silent promotion occurs. |
| `REJECTED` | The policy found an error or disallowed condition. | The batch is blocked before backtesting. |

Each outcome is persisted as immutable evidence through the existing research-evidence boundary, with policy version, timestamp and named issue codes.

## Version 1 checks

| Check | Outcome when violated | Rationale |
|---|---|---|
| Research use case | `REJECTED` / `USE_CASE_NOT_RESEARCH` | Paper/risk data cannot be repurposed as research input. |
| Permitted source kind | `REJECTED` / `SOURCE_KIND_NOT_PERMITTED` | The local policy must name which normalized source kinds it accepts. |
| Minimum history | `REJECTED` / `INSUFFICIENT_HISTORY` | Version 1 requires at least three candles before the strategy/backtest path begins. Individual strategies may require more history. |
| Interval syntax | `QUARANTINED` / `UNSUPPORTED_INTERVAL_POLICY` | The gap policy currently understands positive `m`, `h` and `d` intervals only. |
| Excessive time gap | `QUARANTINED` / `GAP_EXCEEDS_POLICY` | Consecutive gaps larger than three expected intervals require review. This is a conservative local heuristic, not an exchange calendar. |
| Public fallback source | `QUARANTINED` / `PUBLIC_FALLBACK_REQUIRES_REVIEW` | A public fallback can support research investigation but requires review before a run. |

## Workflow boundary

The experiment service validates all selected datasets after its existing comparable-data checks and before it constructs the manifest, invokes the backtester, writes an experiment batch or emits leaderboard data. A rejected or quarantined dataset produces a typed `ResearchDatasetValidationError` naming dataset ID and status.

Qualified deterministic fixtures retain their previous behavior. The validator records an accepted outcome under `research-dataset-v1`; it does not turn fixture values into broker or market evidence.

## Limitations and future work

This version does not recognize NSE/BSE/NFO holidays, special sessions, exchange halts, corporate actions, adjusted/unadjusted price consistency, actual provider freshness, contract expiry, option-chain availability, missing volume policy or point-in-time constituent membership. Those are future, separately approved data/calendar/provider phases.

## Validation

```bash
make lint
make test
```

The regression suite covers accepted qualifying fixtures, rejected insufficient history/use case, quarantined excessive gaps and the experiment preflight block.

This is research and analysis only, not personalized financial advice.
