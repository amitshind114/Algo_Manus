# Local Research Interface

The optional Streamlit interface is a **functional local research workbench**, not a trading engine. It starts in an explicit fixture-data mode so users can exercise the complete local workflow before a later approved broker-data sync stores a validated instrument master and research datasets.

Run it only after installing the optional local UI dependency:

```bash
python -m pip install -e ".[local-ui]"
python -m streamlit run src/algo_manus/ui/app.py
```

Fixture mode lets a user select one or more labelled local sample securities, tune an SMA parameter revision, run the real local experiment/backtest application service, inspect per-security KPI/trade/equity output, sort the multi-security leaderboard and simulate the deterministic paper-risk/event lifecycle. Fixture results are never broker data, real market evidence or a performance claim.

The **Risk & paper** page now initializes and reads a local SQLite control store under `~/.algo-manus/risk_controls.sqlite3` by default. Set `ALGO_MANUS_DATA_DIR` before starting Streamlit to choose another local directory. The page shows the active local central-policy version, durable kill-switch state, append-only control-change history and the latest central decision evidence. Persisting a kill-switch change updates only that local control record; it does not contact a broker or cancel any external order because no external order path exists.

The fixture paper simulator uses local sample marks and a durable local event ledger. The **Risk & paper** page replays that ledger against an explicit ₹100,000 fixture starting cash to show local cash, long-only positions, realised P&L and order state. Its event record carries persisted policy/kill-state identity when a fixture proposal is evaluated, but it is not a broker-confirmed order, paper-market fill or reconciliation result. See `docs/LOCAL_PAPER_PROJECTION.md` for replay assumptions and limitations.

The same page derives a local portfolio-risk snapshot from that replay and explicitly displayed fixture marks. It displays fixture gross/instrument exposure, realised-loss utilisation and the active concentration cap before a local simulation is evaluated. The values are local policy inputs, not market valuation or broker reconciliation. See `docs/LOCAL_PORTFOLIO_RISK.md` for central-limit definitions and the strict local-data boundary.

Before enabling the local fixture-paper button, the workbench now resolves the selected experiment to a persisted immutable research manifest and the exact accepted validation outcome for its selected dataset. The paper decision retains those evidence identifiers. Session-only experiment state from before this promotion gate is blocked until a persisted fixture experiment is run. See `docs/RESEARCH_TO_PAPER_PROMOTION.md` for the evidence chain and limitations.

Fixture experiments are also saved in the local SQLite experiment store and appear in the sidebar count, **Multi-test leaderboard** and **Reporting & analytics** after a Streamlit restart. Those pages allow selecting a persisted batch and show its linked manifest ID before rendering stored KPI summaries. New fixture results also retain bounded local equity-curve and completed-trade artifacts: **Backtesting** reads the selected result’s saved detail and **Reporting** reads the selected batch’s saved trade rows after restart. Older summary-only local batches show an explicit detail-unavailable warning and are never silently recalculated. See `docs/LOCAL_EXPERIMENT_ARTIFACTS.md` for retention defaults and limitations. This is local fixture history only, not a broker-data or performance-record system.

The **Experiment history** section in **Multi-test leaderboard** now exposes read-only local artifact integrity for every stored batch/result. It reports complete, unavailable, incomplete or result-spec-mismatched detail with expected/actual local row counts, and provides a status filter. The view reads SQLite evidence only; it never repairs records, recomputes fixtures, validates broker data or changes paper-promotion eligibility. See `docs/LOCAL_EXPERIMENT_ARTIFACT_INTEGRITY.md` for the status rules and limits.

The local strategy catalog is now backed by an explicit in-process registry. The SMA crossover is the only registered reference implementation. Each future strategy must declare versioned metadata, supported instrument types and intervals, a strict parameter schema, risk notes and pure signal behavior. Strategies cannot receive database, provider, broker, UI or execution access; they may not submit orders directly.

The interface cannot authenticate a broker, fetch market data, bypass paper risk policy or enable live execution. Those responsibilities stay in provider adapters and application services, with separate approval gates. After a broker-master and research-data gate is approved, the same workbench controls will move from labelled fixture inputs to validated broker-authoritative instruments and datasets.

This is research and analysis only, not personalized financial advice.
