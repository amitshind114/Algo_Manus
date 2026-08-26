# Read-Only Retained-Evidence Manifest Comparison

## Purpose and non-authoritative boundary

Option Q compares **two already-built retained-evidence manifests** in memory. Each side is identified by a retained experiment batch, retained instrument result, and optional exact retained paper-run evidence ID. The result says only whether the selected export-safe payloads are `IDENTICAL` or `DIFFERENT`, and when different, names the paths and values that differ.

> A manifest comparison is a descriptive integrity view. It is not a winner, score, recommendation, reconciliation, data-quality finding, source verification, promotion decision, paper approval, risk clearance, order authority, or execution record.

The comparison does not persist a comparison artifact, mutate either manifest, rebuild a strategy, refresh data, inspect a manual reference, contact a service, run timed work, or schedule any process. It has no merge, select, approve, promote, submit, cancel, publish, or execution operation.

## Comparison inputs and result

| Item | Behavior | Explicit limit |
|---|---|---|
| Left and right selection | Each side builds the existing Option P retained-evidence manifest from exact retained identifiers. | The comparison does not infer a preferred paper-run row or substitute a similar batch, dataset, instrument, or review record. |
| Identity state | Payloads with no safe-path differences and the same manifest digest return `IDENTICAL`. | Identical means only that the retained export-safe views match under this implementation. |
| Difference state | Distinct safe values return `DIFFERENT` with deterministic, category-then-path ordered rows. | A difference is descriptive; it never ranks, explains causality, or makes either selection eligible. |
| Missing or mismatched retained evidence | The existing Option P manifest records its named condition, such as a missing research manifest, batch instrument, paper-run evidence, robustness record, or dataset review. The comparison reports the safe condition difference. | No fallback, repair, reconciliation, or record creation occurs. Blank required batch/instrument inputs remain rejected by the manifest builder. |

## Safe difference categories

The service recursively compares a defensive allowlist rather than arbitrary input content. Each difference is placed in one category.

| Category | Examples of included paths | Interpretation limit |
|---|---|---|
| `lineage` | Selected batch/instrument/paper IDs, experiment and manifest IDs, universe/snapshot IDs, dataset IDs, source name/kind, content fingerprints, result-spec IDs, linkage state | An identifier or fingerprint mismatch is not evidence that one source or result is correct. |
| `policy` | Validation, paper, robustness and review policy versions; execution assumptions; split-policy fields | A policy difference does not validate, approve, or choose a policy. |
| `parameter` | Strategy parameter revision IDs and retained candidate parameter-status identifiers | No candidate is scored, selected, or rerun. |
| `timestamp` | Creation, evaluation, retrieval, split-boundary, manifest-range, and information-cutoff timestamps | A newer timestamp is not automatically preferable or current. |
| `blocker` | Manifest conditions, retained blocking reasons, and linkage conditions | A named blocker is retained context, not a newly evaluated gate result. |
| `hash` | Synthetic `verification.sha256` row when the left and right canonical manifest digests differ | The digest is an integrity reference, not a signature or upstream-source verification. |

## Canonical hash semantics

Option Q does **not** recalculate or redefine either Option P manifest digest. It compares the retained `manifest_sha256` values and, when they differ, adds one `hash` row at `verification.sha256`. Each manifest hash still covers the Option P canonical payload: UTF-8 JSON with sorted keys and compact `(',', ':')` separators, with verification metadata excluded before hashing.

Consequently, identical selected retained evidence rebuilt after restart remains comparable with the same canonical payload and digest. A different digest means the canonical retained payloads differ; it does not establish the correctness, completeness, origin, recency, market relevance, or authorization of any underlying record.

## Secret, manual-reference, and detail exclusions

The comparison allowlist preserves Option P's exclusions. It never emits manual corporate-action/calendar reference contents, review notes, source URIs, raw source payloads, credentials, tokens, detailed trade rows, equity curves, price series, or other arbitrary fields inserted into an invalid input object. The Reporting page reads its selections through the workbench application service and only renders safe category, path, left-value, and right-value rows.

Fixture selections remain deterministic local sample evidence. They are not broker data, live market data, account data, corporate-action or calendar verification, performance proof, or a recommendation. A retained manual review remains a local declaration; neither manifest construction nor comparison opens or verifies its reference.

## Workbench behavior

In **Reporting & analytics**, the **Compare two retained-evidence manifests** expander shows left and right retained selectors, both hashes, and either an `IDENTICAL` notice or a table of ordered named differences. The text explicitly states that the view does not indicate a better selection, eligibility, or action. It includes no control to change evidence, repair data, retrieve a feed, contact a broker, modify risk, start paper work, submit/cancel an order, or enable execution.

This is research and analysis only, not personalized financial advice.
