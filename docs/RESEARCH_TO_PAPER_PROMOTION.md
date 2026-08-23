# Research-to-Paper Promotion Gate

## Purpose

Phase 5B prevents the local paper simulator from accepting a proposal merely because the UI can construct a fixture-shaped validation object. A proposal must instead resolve to a **persisted experiment batch**, its immutable **research manifest**, and the exact **accepted validation outcome** for the selected instrument’s dataset.

## Required local evidence chain

| Required record | Validation performed | Local outcome when absent or inconsistent |
|---|---|---|
| Experiment batch | The selected batch exists and references a manifest. | The workbench disables the local paper proposal. |
| Research manifest | The referenced immutable manifest exists. | Promotion cannot resolve. |
| Instrument result | The selected paper instrument belongs to the batch. | Promotion cannot resolve. |
| Parameter revision | Manifest and batch parameter-revision IDs agree. | Promotion cannot resolve. |
| Dataset validation | The selected result’s dataset has an exact accepted manifest validation outcome. | Promotion cannot resolve. |

The workbench stores fixture experiments and manifests locally under the configured `ALGO_MANUS_DATA_DIR`. A pre-existing session-only experiment is deliberately blocked after upgrade until a new persisted fixture experiment is run.

## Paper decision evidence

For a resolved local promotion, the append-only `RISK_DECISION` event contains these identifiers:

| Field | Meaning |
|---|---|
| `research_batch_id` | Local persisted experiment batch selected for promotion. |
| `research_manifest_id` | Immutable manifest reproducing the research inputs and assumptions. |
| `research_dataset_id` | Dataset attached to the selected instrument result. |
| `research_validation_policy_version` | Validation policy that accepted that dataset. |

When the local paper service is configured to require promotion evidence and no such evidence is supplied, it records a blocked local proposal with `RESEARCH_EVIDENCE_MISSING`. It does not create a simulated submission or fill.

## Strict limits

This links local fixture research evidence to local fixture paper simulation. It does **not** establish broker-authoritative data, real market validation, broker account permission, exchange acknowledgement, paper-market fill or live trading readiness. The evidence chain must be separately revalidated when a future approved broker/data phase introduces a broker master or real datasets.

## Validation

```bash
make lint
make test
```

Regression tests cover persisted fixture resolution, unknown/ineligible promotion rejection, missing-evidence blocking and retention of exact evidence identifiers in the append-only paper decision event.

This is research and analysis only, not personalized financial advice.
