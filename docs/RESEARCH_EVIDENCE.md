# Research Manifests, Data Lineage and Validation Evidence

## Scope

Phase 2A defines the immutable evidence contracts that future backtests and experiments must carry. It does not fetch data, add a provider, modify the existing experiment runner, change fixture behavior or mark any strategy as paper-eligible.

## Research-run manifest

`ResearchRunManifest` is the durable vocabulary for a reproducible multi-security research run. Its deterministic `manifest_id` changes only when reproducibility-relevant evidence changes; its creation timestamp intentionally does not change the identity.

| Evidence group | Manifest fields |
|---|---|
| Strategy evidence | Strategy ID, semantic version and immutable parameter revision ID. |
| Universe evidence | Universe ID and pinned instrument-master snapshot ID. |
| Data evidence | Dataset ID, instrument, interval, provider/source identity, source URI, retrieval time, raw-content checksum, adjustment basis and permitted use case. |
| Quality evidence | Exactly one named validation outcome for each dataset, including policy version and issues. |
| Engine evidence | Engine version, starting cash, quantity, commission/slippage, force-close rule and execution-timing policy. |
| Time evidence | Start, end, information cutoff and a creation timestamp; all timestamps are timezone-aware. |
| Code evidence | Optional lower-case Git commit identifier when the source revision is known. |

The manifest accepts only `RESEARCH` datasets and only validation outcomes with status `ACCEPTED`. A quarantined or rejected dataset cannot be silently included in a research manifest.

## Dataset lineage

`DatasetLineage` is derived from the existing immutable `CandleDataset` and `DataProvenance` contracts. It does not copy bars or provider client state. Its purpose is to preserve the data evidence required to explain a future result without allowing a UI screen to substitute a source or invent a freshness status.

| Data validation status | Meaning | Research manifest eligibility |
|---|---|---|
| `ACCEPTED` | The declared policy completed without an error-severity issue. | Eligible. |
| `QUARANTINED` | A named issue requires review; no silent promotion is permitted. | Not eligible. |
| `REJECTED` | The policy found an invalid or disallowed dataset. | Not eligible. |

Each issue carries a stable code, severity and human-readable message. An accepted outcome cannot contain an error-severity issue, and a non-accepted outcome must name at least one issue.

## Local storage and read boundary

The default local implementation is `SqliteResearchEvidenceRepository`. It persists manifests, lineages, validation outcomes and validation issues using a component-level schema version, foreign-key integrity and short-lived SQLite connections. Existing immutable manifest IDs are idempotent; an attempt to write different validation content under the same dataset/policy key fails explicitly rather than overwriting evidence.

`ResearchEvidenceReadService` provides a narrow, read-only local query path for a future Backtests/Experiments evidence panel. It can retrieve one manifest by ID or return recent persisted manifests. It does not calculate a KPI, alter a backtest or mutate paper state.

The storage implementation remains local SQLite only. A future database implementation may satisfy the same repository boundary, but no cloud database, data provider, broker or background service is implied by this capability.

## Integrated experiment workflow

The multi-security experiment application service now creates an `ACCEPTED` local research manifest only after it has confirmed comparable research-use datasets and completed the existing backtest calculations. The manifest is persisted before the batch is saved, and the batch retains the immutable `research_manifest_id` reference. Existing batch ID calculation, backtest specifications, trades, leaderboard rows and fixture values are unchanged.

`ExperimentEvidenceReadService` joins an existing persisted batch to the manifest it references and returns a typed read-only view. A future terminal evidence panel can use this view to show the true snapshot, strategy version, dataset checksum and execution assumptions rather than derive those facts from UI session state.

## What this phase does not claim

The presence of a manifest does not prove data quality, profitability, robustness, paper eligibility or live readiness. Fixture datasets remain clearly labelled fixtures. Real provider/adaptor work, point-in-time source availability, portfolio allocation, walk-forward validation and promotion gates require separately approved future phases.

## Validation

```bash
make lint
make test
```

The suite verifies deterministic IDs across different creation times, rejects non-research/quarantined/rejected inputs, blocks a validation outcome that attempts to silently accept an error, round-trips evidence through SQLite, rejects conflicting immutable outcomes, releases database handles for local file cleanup and proves experiment batches retain a retrievable manifest reference without changing leaderboard output.

This is research and analysis only, not personalized financial advice.
