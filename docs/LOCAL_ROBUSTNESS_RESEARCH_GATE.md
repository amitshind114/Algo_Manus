# Local Robustness Research Gate

## Purpose and boundary

Option K adds a **bounded, local research-evidence evaluator**. It is intended to make one limited question inspectable: whether a small, declared set of parameter revisions produces retained in-sample and holdout backtest records under the same deterministic engine and declared costs. It is not an optimizer, strategy selector, recommendation engine, paper-approval mechanism, or execution capability.

> A robustness record is an auditable local research artifact. It is **not** evidence that a strategy is profitable, suitable, durable, ready for paper trading, or likely to perform in the future.

| Area | Implemented local boundary | Explicitly not implied |
|---|---|---|
| Data | One existing `RESEARCH`-use candle dataset, identified by immutable dataset ID | Data completeness, point-in-time corporate-action correctness, survivorship control, current market availability, or data-provider validation |
| Parameters | A small, caller-declared Cartesian grid with a hard cap of 64 cells | Unbounded tuning, automatic search, candidate selection, ranking, or optimization |
| Evaluation | Separate chronological in-sample and holdout backtests through the existing next-bar engine | A performance certificate, future return prediction, or proof of robustness |
| Retention | Immutable local SQLite evidence with deterministic content identity | Broker confirmation, a trusted timestamp, signed audit trail, cloud backup, or external reconciliation |
| Workflow | Informational display only | Paper promotion, risk approval, order submission, broker access, or live execution |

## Deterministic partition policy

The policy is recorded with every evidence record. Given `n` ordered closed candles, an in-sample ratio `r`, and positive embargo count `b`, the service calculates `s = floor(n × r)` and uses the following exact intervals.

| Partition | Candle indices | Purpose |
|---|---|---|
| In-sample | `[0, s)` | Evaluated independently against each declared parameter revision |
| Embargo | `[s, s + b)` | Deliberately excluded from both evaluations |
| Holdout | `[s + b, n)` | Evaluated independently using only later candles |

No records are shuffled, randomly sampled, or silently moved between partitions. The service rejects a policy that cannot create both an in-sample and holdout partition. A candidate that lacks enough bars for its strategy’s declared history requirement in either partition is retained as `INSUFFICIENT_HISTORY`; it is not silently recalculated on more data, substituted with a fixture, or treated as a passing result.

Each eligible partition uses the established bar backtester. A signal derived from closed bar *t* can only fill at the open of bar *t + 1*. The in-sample and holdout datasets are created independently, so no holdout candle enters the in-sample backtest and no in-sample position, signal, or state is carried into the holdout backtest.

## Bounded-grid policy

The caller supplies a non-empty mapping of named strategy parameters to one or more candidate values. The service verifies parameter names against the selected registered strategy and validates every Cartesian-grid cell through the existing shared parameter schema before any backtest is run. Invalid, unknown, or cross-field-invalid values fail explicitly. The policy cap must be between 1 and 64 cells; a larger grid is rejected rather than truncated or partially evaluated.

The workbench demonstrates a deliberately fixed four-cell SMA crossover grid, a 60% chronological in-sample segment, and a one-bar embargo. Its data is explicitly labelled deterministic fixture data. This visible demonstration must never be interpreted as broker data, market evidence, or an invitation to choose one row over another.

## Retained immutable evidence

Successful and insufficient-history evaluations are stored in local `robustness_evidence.sqlite3` under the configured `ALGO_MANUS_DATA_DIR` (default `~/.algo-manus`). The repository is append-only at the contract level: saving the same evidence ID with identical content is idempotent, while a different payload under that immutable ID fails explicitly.

| Retained field group | Examples |
|---|---|
| Source and strategy lineage | Original dataset ID, strategy ID/version, candidate parameter values, candidate parameter-revision ID |
| Partition policy | Policy version, in-sample ratio, positive embargo bars, in-sample end, holdout start |
| Execution assumptions | Initial cash, quantity, commission basis points, slippage basis points, force-close-at-end, next-bar execution result identifiers |
| Outcomes | Candidate state, in-sample and holdout result-spec IDs, net P&L, return, trade count, and calculation outcome where eligible |
| Gate context | `INFORMATIONAL_ONLY` or `INSUFFICIENT_HISTORY`, explicit selection-bias warning, local creation time |

The deterministic evidence identifier includes the source dataset, strategy/version, declared grid, complete partition policy, and execution assumptions. It deliberately does **not** identify a preferred candidate. Existing `ResearchRunManifest`, experiment, paper-promotion, central-risk, and append-only paper-event rules are unchanged. Robustness evidence does not substitute for a retained research manifest and accepted validation outcome, and it cannot satisfy the separate deterministic paper-risk gate.

## Interpretation limits and warnings

The evaluator always retains a selection-bias and overfitting warning. Even a declared small grid and a chronological holdout do not prevent researcher degrees of freedom, repeated experimentation, sample dependence, multiple-testing effects, regime change, implementation error, cost-model error, or hidden data-quality defects. A result with no trades, few trades, a negative return, or an insufficient partition is evidence of that computed local state only; it is not a trading signal.

Historical datasets can be stale, incomplete, synthetically adjusted, affected by corporate actions, biased by symbol/instrument survivorship, or otherwise unsuitable for a question. Broker-retained historical data remains research evidence only. Fixture data remains solely a workflow demonstration. Users must independently validate market data, corporate actions, survivorship methodology, liquidity and execution assumptions before relying on any analysis.

## Capability exclusions

Option K adds no broker account, profile, funds, RMS, holdings, positions, LTP/live-price, WebSocket, historical-data download, order, cancellation, paper broker, scheduler, worker, cloud deployment, external queue, autonomous execution, or recommendation capability. The workbench calls application services only and exposes no action that selects a strategy, promotes a strategy, approves paper activity, or routes an order.

This is research and analysis only, not personalized financial advice.
