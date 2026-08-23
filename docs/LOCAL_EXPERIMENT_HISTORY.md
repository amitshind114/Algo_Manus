# Local Experiment History

## Scope

Phase 6A makes local fixture experiment history restart-safe. The fixture workbench writes batches to local SQLite together with their immutable research-manifest link. On each workbench startup, the sidebar, multi-security leaderboard and reporting page load this persisted local history rather than relying only on Streamlit session state.

## Stored evidence

| Item | Persisted locally | Used after restart |
|---|---|---|
| Experiment batch identity | Yes | Select a saved local experiment. |
| Universe, snapshot, strategy and parameter revision | Yes | Display research context and reproduce identifiers. |
| Research manifest ID | Yes | Show evidence linkage and support paper-promotion checks. |
| Per-instrument KPI summary | Yes | Populate leaderboard and reporting aggregate metrics. |
| Detailed equity curve and trade rows | No | Not reconstructed in the restart list; re-run the fixture experiment for local detail inspection. |

## Workbench behavior

The newest persisted experiment becomes the active local batch on restart. The **Multi-test leaderboard** and **Reporting & analytics** pages each provide a persisted-batch selector. Selecting a record updates the active local batch for subsequent local review. The sidebar count reflects only the stored local fixture batches, not stale session objects.

## Limits

This local history is not a market-data warehouse, broker audit record, cloud backup, tax statement, order-management system or performance certification. All source data in this workbench remains deterministic fixture data. Broker-authoritative master data, actual research datasets, real paper observation and any execution connection remain separately gated.

## Validation

```bash
make lint
make test
```

Regression coverage proves a persisted fixture batch and its manifest link can be listed after a fresh service instance, and that invalid history limits fail explicitly.

This is research and analysis only, not personalized financial advice.
