# Local Research Interface

The optional Streamlit interface is a **functional local research workbench**, not a trading engine. It starts in an explicit fixture-data mode so users can exercise the complete local workflow before a later approved broker-data sync stores a validated instrument master and research datasets.

Run it only after installing the optional local UI dependency:

```bash
python -m pip install -e ".[local-ui]"
python -m streamlit run src/algo_manus/ui/app.py
```

Fixture mode lets a user select one or more labelled local sample securities, tune an SMA parameter revision, run the real local experiment/backtest application service, inspect per-security KPI/trade/equity output, sort the multi-security leaderboard and simulate the deterministic paper-risk/event lifecycle. Fixture results are never broker data, real market evidence or a performance claim.

The interface cannot authenticate a broker, fetch market data, bypass paper risk policy or enable live execution. Those responsibilities stay in provider adapters and application services, with separate approval gates. After a broker-master and research-data gate is approved, the same workbench controls will move from labelled fixture inputs to validated broker-authoritative instruments and datasets.

This is research and analysis only, not personalized financial advice.
