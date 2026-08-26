# Read-Only Retained-Evidence Manifest

## Purpose and non-authoritative boundary

Option P builds one deterministic local JSON manifest for a selected retained experiment batch, retained instrument result, and optionally selected retained paper-run evidence row. It combines only identifiers, policies, timestamps, named blockers, bounded lineage, result-spec metadata, and SHA-256 fingerprints already stored locally.

> A retained-evidence manifest is an integrity-oriented local report. It is not a signature, source verification, broker confirmation, market-data certificate, data-quality determination, strategy recommendation, promotion, paper approval, risk clearance, order authority, or execution record.

The manifest is generated in memory for display and local download. It does not persist a new record, mutate the selected batch or any other evidence, open a local reference, fetch data, contact an external service, or schedule any work.

## Selection and retained content

| Selected input | Included retained metadata | Intentionally excluded |
|---|---|---|
| Experiment batch | Batch ID, creation time, status, universe/snapshot IDs, strategy, parameter revision, and research-manifest ID | Performance ranking and any new calculation |
| Research manifest | Manifest ID, strategy/version, parameter revision, engine version, dates, bounded data lineage IDs/fingerprints, validation status/issue codes, and execution assumptions | Source URI and raw source payload |
| Instrument result | Instrument ID, dataset ID, result-spec ID, stored trade/equity point counts | Detailed trades, equity curve, price series, and recalculation |
| Paper-run evidence | Evidence ID, state, linked IDs, policies, timestamp, and blockers | Any change to promotion, risk, or paper state |
| Robustness evidence | Evidence ID, split policy, boundaries, candidate IDs/statuses, state, timestamp, and warning | Candidate ranking, selection, or new backtest |
| Dataset-review evidence | Evidence ID, state, dataset/instrument/provenance IDs, policy, timestamp, and blockers | Corporate-action/calendar reference values and manual notes |
| Option N linkage | Link state, exact linked review ID, and named conditions | Similar-record fallback or automatic remapping |

## Canonicalization and hash

The payload excludes the verification object when it is canonicalized. Canonical bytes are UTF-8 JSON with `sort_keys=true` and compact `(',', ':')` separators. The exported `verification.sha256` equals the SHA-256 digest of those canonical bytes. Rebuilding the same selected retained evidence after restart therefore produces the same canonical payload and digest.

The digest only indicates that the payload can be reproduced from those retained values under this exact canonicalization rule. It does not prove that upstream data, manual declarations, source content, market conditions, or execution records are correct or complete.

## Explicit conditions and no fallback

The manifest carries a sorted `conditions` list. Examples include `RESEARCH_MANIFEST_EVIDENCE_MISSING`, `BATCH_INSTRUMENT_EVIDENCE_MISSING`, `PAPER_RUN_EVIDENCE_MISSING`, `PAPER_RUN_EVIDENCE_ID_MISMATCH`, `PAPER_RUN_EVIDENCE_SELECTION_REQUIRED`, `ROBUSTNESS_EVIDENCE_MISSING`, `DATASET_REVIEW_EVIDENCE_MISSING`, retained paper blockers, and Option N linkage conditions.

If zero or several retained paper-run rows match a batch/instrument, the service does not infer a preferred result. It uses the only match when exactly one exists; otherwise it reports missing evidence or requires the caller to select an exact retained paper-evidence ID. It never substitutes a same-symbol, near-date, or similar dataset record.

## Secret and sensitive-content exclusion

The payload declares that manual reference contents, review notes, source URIs, credentials/tokens, detailed trades, and equity curves are excluded. The workbench only receives locally retained IDs and fields from the application service; it does not request a secret, authenticate, upload, transmit, or verify a source.

## Workbench behavior and limitations

In **Reporting & analytics**, the **Selected retained-evidence manifest** expander permits selection of an already-retained batch instrument and, when applicable, an exact retained paper-run evidence ID. It shows schema and hash, lists named conditions, and provides a local JSON download. It has no control to record evidence, refresh data, repair a record, promote a strategy, approve paper activity, alter risk, submit/cancel an order, contact a broker or feed, run timed work, or enable execution.

All fixture content remains deterministic local sample evidence—not broker data, live market data, corporate-action data, calendar data, account data, performance proof, or a recommendation. Manual review evidence is still only a declaration; the manifest does not inspect its reference or make it authoritative.

This is research and analysis only, not personalized financial advice.
