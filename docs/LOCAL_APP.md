# Local Research Interface

The optional Streamlit interface is a **thin local shell**, not a trading engine. It intentionally starts in a disabled, empty state until a later approved broker-data sync stores a validated local instrument master and research datasets.

Run it only after installing the optional local UI dependency:

```bash
python -m pip install -e ".[local-ui]"
python -m streamlit run src/algo_manus/ui/app.py
```

The interface cannot authenticate a broker, fetch market data, calculate strategy signals, bypass paper risk policy or enable live execution. Those responsibilities stay in provider adapters and application services, with separate approval gates.

When the remaining read models are wired in, the interface will let the user select validated securities from the broker snapshot, choose an immutable parameter revision, launch an application-level research experiment, inspect the KPI leaderboard and view paper-event history.

This is research and analysis only, not personalized financial advice.
