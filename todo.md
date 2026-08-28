# Active delivery checklist

## Option B — authenticated read-only Angel One historical candles

- [x] Inspect the existing market-data port, dataset contracts, immutable repositories and local UI composition boundary.
- [x] Confirm current Angel One connector availability and document secure local configuration requirements without requesting or storing secrets in chat, source or tests.
- [x] Verify the official historical-candle request and response contract from Angel One documentation.
- [x] Design a manual-only authenticated historical-data ingestion workflow with typed request validation, local source evidence and immutable dataset persistence.
- [x] Implement the read-only adapter and application service without account, order, WebSocket, scheduler, paper-price or execution capabilities.
- [x] Add deterministic contract, failure, persistence, restart and no-prohibited-capability regression tests.
- [x] Expose source status and explicit manual historical-data retrieval in the local workbench through application services only.
- [x] Update documentation with Option B scope, credential isolation, evidence semantics, limits and Option C deferral.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option B changes to `main`, then report completion and request separate Option C security approval.

## Option C — local Angel One session handling security phase

- [x] Inspect official session-generation and token-refresh requirements plus current local configuration, secret-ignore and market-data boundaries.
- [x] Design a manual-only local session lifecycle that limits secret exposure, prevents persistence/logging and defines expiry/failure behavior.
- [x] Implement typed session acquisition and short-lived access-token handoff to the existing read-only historical adapter without account, order, market-price, WebSocket, scheduler or execution capabilities.
- [x] Add deterministic session-contract, failure, no-secret-exposure, no-prohibited-capability and adapter-integration regression tests.
- [x] Expose only display-safe local session readiness and manual lifecycle controls through application services; never render or accept raw secrets in the UI.
- [x] Update local configuration guidance and documentation with Option C security limits, rotation/expiry behavior and the remaining capability gates.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option C changes to `main`, then report completion and identify the next approval gate.

## Option D — retained broker historical dataset backtest integration

- [x] Inspect the backtest application, research manifest, experiment evidence and immutable candle-dataset contracts for a safe selected-dataset integration point.
- [x] Design explicit dataset selection, source/evidence pinning, fixture separation and no-lookahead validation rules.
- [x] Implement a research-only retained-dataset backtest path without any additional broker request, account, price, WebSocket, scheduler or execution capability.
- [x] Add deterministic selection, evidence lineage, invalid/unaccepted dataset, no-lookahead and fixture-regression tests.
- [x] Expose only retained-dataset metadata, selection and bounded research results through application services in the local workbench.
- [x] Update documentation with Option D data provenance, data-quality caveats, fixture distinction and remaining capability gates.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option D changes to `main`, then report completion and request the next separate approval.

## Algo Manus primary-build architecture reconciliation

- [x] Audit the current codebase against the attached production blueprint, identifying implemented foundations, partial components, missing integrations and explicit capability exclusions.
- [x] Convert the blueprint into a dependency-ordered vertical-slice roadmap for Algo Manus, retaining its local-first research/paper scope and separating any live capability behind later approvals.
- [x] Define the first auditable end-to-end paper-operation slice from retained data through strategy, deterministic risk decision, event evidence, simulated outcome and reporting.
- [x] Document the architecture decisions, regulatory assumptions requiring current broker/exchange verification, and a strict no-live-execution gate.
- [x] Validate the roadmap against existing tests and source boundaries, commit the reconciliation documentation, and request approval for the first implementation slice.

## Option E — canonical paper event spine and event-derived projections

- [x] Audit the existing paper ledger, execution contracts, central risk engine, risk-control persistence and projection services for canonical integration seams.
- [x] Define one immutable paper-event lifecycle for proposal, risk decision, accepted/rejected, working, partial fill, fill, cancellation and reconciliation outcomes.
- [x] Implement the application service so every accepted paper lifecycle path records a deterministic risk decision before any accepted order event.
- [x] Implement replay-safe position and P&L projections derived solely from retained fill and reconciliation events, never from order intent or mutable UI state.
- [x] Add deterministic lifecycle, risk-ordering, partial-fill, cancellation, replay, duplicate/restart and no-broker-capability tests.
- [x] Expose display-safe paper-event timeline, projected positions and projected P&L through application-service read paths only.
- [x] Update local documentation with simulation assumptions, event evidence, explicit exclusions and remaining reconciliation limitations.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option E changes to `main`, then report completion and request the next separate build approval.

## Option F — conservative local limit-fill simulator and reconciliation scenarios

- [x] Inspect the Option E event contracts, local execution service, projector and workbench to define a minimal compatible simulator boundary.
- [x] Define explicit local-only assumptions for limit eligibility, volume-capped partial fills, adverse slippage, no-fill and unsupported market-order rejection.
- [x] Add failing deterministic acceptance tests for limit eligibility, no-fill, partial/final fills, cancellation, duplicate requests, restart replay and reconciliation evidence.
- [x] Implement the deterministic simulator through application services only, retaining each simulation decision as immutable local event evidence.
- [x] Expose display-safe simulator assumptions and scenario outcome evidence through the existing local paper read paths only.
- [x] Document simulation assumptions, non-claims, exclusion of broker market data/order-book realism, and reconciliation limits.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option F changes to `main`, then report completion and request the next separate approval.

## Option G — local event-bus boundary and event wiring audit

- [x] Audit existing research and paper direct service flows, durable evidence stores and UI composition points for safe event publication seams.
- [x] Define immutable local event envelopes, event types, dispatch policy, subscriber isolation, ordering, failure and retention semantics without external queue or background processing.
- [x] Add failing deterministic acceptance tests for publication order, subscriber isolation, duplicate safety, durable audit records, restart boundary and prohibited external capability absence.
- [x] Implement the in-process local event bus and wire bounded research/paper lifecycle publication through application services only.
- [x] Expose a display-safe, read-only local event-wiring audit through the workbench without making any operation actionable.
- [x] Document the in-process boundary, non-durable/restart behavior, explicit local-only limits and evolution path to a future external event infrastructure only if approved.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option G changes to `main`, then report completion and request the next separate approval.

## Option H — event-derived local paper-operations console

- [x] Audit existing paper projection, audit, risk and wiring read services and define one display-safe operations-console contract.
- [x] Add failing deterministic tests for lifecycle/risk/simulator/reconciliation/wiring aggregation, empty evidence, malformed-event isolation and no-actionable capability.
- [x] Implement an application read model derived only from immutable local evidence and bounded current-process wiring diagnostics.
- [x] Expose the local operations console through the existing Risk & paper workbench without direct ledger, provider or broker calls.
- [x] Document local-only console semantics, evidence scope, no-live exclusions and restart limitations for in-process diagnostics.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option H changes to `main`, then report completion and request the next separate approval.

## Option I — India-first instrument lifecycle enrichment

- [x] Audit current local instrument contracts, snapshot persistence, availability/review handling and workbench reads for India-market contract metadata seams.
- [x] Define failing deterministic acceptance tests for exchange/segment/tradingsymbol/expiry/strike/option type/lot/tick/status lifecycle, conflicts, deactivation and review requirements.
- [x] Implement canonical India-first instrument contract enrichment and local lifecycle/review projections without a new broker endpoint or market-price capability.
- [x] Expose display-safe local instrument lifecycle, contract metadata and review-status reads through application services in the workbench.
- [x] Document canonical local instrument metadata, snapshot/review semantics, explicit data freshness limits and no-broker/no-live exclusions.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option I changes to `main`, then report completion and request the next separate approval.

## Option J — strategy-family hardening and research-gate comparison

- [x] Audit current strategy registry, SMA implementation, backtest engine, research evidence, promotion rules and workbench comparison reads for safe extension seams.
- [x] Define failing deterministic acceptance tests for the second strategy’s parameter validation, no-lookahead fills, reproducibility, evidence outputs, comparison and promotion-gate compatibility.
- [x] Implement a second conservative versioned local strategy and register it without changing or weakening SMA crossover behavior.
- [x] Integrate the strategy with immutable research artifacts, comparable local results and existing paper-promotion evidence gates.
- [x] Expose display-safe strategy-family comparison and evidence/gate status reads in the workbench without recommendations or actionable order controls.
- [x] Document strategy assumptions, local simulation limits, no-performance claims, selection bias limits and no-live exclusions.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option J changes to `main`, then report completion and request the next separate approval.

## Option K — robustness and research-evidence gate

- [x] Audit current dataset, backtest, experiment, artifact and promotion-evidence contracts for deterministic local robustness evaluation seams.
- [x] Define failing deterministic acceptance tests for chronological in-sample/holdout partitioning, bounded parameter grids, reproducibility, insufficient-history handling, warnings and no-actionable capability.
- [x] Implement local-only robustness evaluation with declared split policy, bounded grid validation, next-bar backtests and explicit selection-bias warnings.
- [x] Retain robustness evidence with immutable local research lineage and expose it through an application read service without changing paper-promotion or risk gates.
- [x] Expose a display-safe robustness-gate summary and evidence rows in the workbench without strategy selection, recommendation, promotion or order controls.
- [x] Document robustness assumptions, non-claims, overfitting/selection-bias limits, dataset limitations and no-live exclusions.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option K changes to `main`, then report completion and request the next separate approval.

## Option L — explicit local paper-run eligibility and evidence gate

- [x] Audit the existing paper-promotion resolver, deterministic risk evidence, retained experiment/manifest validation, robustness evidence and local paper ledger seams.
- [x] Define failing deterministic acceptance tests for explicit eligibility states, named blocking reasons, immutable evidence identity, restart retention, stale/missing evidence refusal and no-actionable capability.
- [x] Implement a local read/evaluation service that resolves declared research, validation, robustness and risk evidence without changing promotion, risk or paper-event semantics.
- [x] Retain immutable local eligibility evidence and expose it through an application read service without broker, market-data, order, cancellation, scheduler, worker or execution capability.
- [x] Expose a display-safe eligibility/evidence view in the workbench without any approval, promotion, order or paper-run control.
- [x] Document eligibility semantics, blocking-reason interpretation, evidence limitations, fixture distinction and strict no-live exclusions.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option L changes to `main`, then report completion and request the next separate approval.

## Option M — local corporate-action and calendar-review evidence gate

- [x] Audit retained dataset lineage, validation, promotion, robustness and paper-run evidence seams for a separate review gate.
- [x] Define failing deterministic acceptance tests for explicit review records, declared review scope, missing/stale/unresolved blockers, immutable identity, restart retention and no-actionable capability.
- [x] Implement immutable local corporate-action and calendar-review evidence with declared review policy, explicit scope, named blockers and no data retrieval capability.
- [x] Expose a display-safe review-evidence summary in the workbench without promotion, approval, order, paper-run, broker, feed, scheduler or execution controls.
- [x] Document review semantics, fixture distinction, data/corporate-action/calendar limitations and strict no-live exclusions.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option M changes to `main`, then report completion and request the next separate approval.

## Option N — read-only cross-evidence linkage view

- [x] Audit retained dataset-review and paper-run eligibility evidence lineage, repository and workbench composition seams.
- [x] Define failing deterministic acceptance tests for matched linkage, missing review evidence, blocked review evidence, dataset/instrument mismatch, restart-safe reads and no-actionable capability.
- [x] Implement a local read-only linkage service that joins retained paper-run eligibility and dataset-review evidence without changing either record or downstream gate semantics.
- [x] Expose a display-safe cross-evidence linkage view in the workbench without approval, promotion, order, paper-run, broker, feed, scheduler or execution controls.
- [x] Document linkage semantics, named mismatch conditions, fixture/manual-declaration limitations and strict no-live exclusions.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option N changes to `main`, then report completion and request the next separate approval.

## Option O — read-only evidence freshness and lineage-coverage dashboard

- [x] Audit retained robustness, paper-run, dataset-review and cross-evidence timestamps, states, repositories and workbench composition seams.
- [x] Define failing deterministic acceptance tests for declared freshness policy, stale/current/unknown coverage, blocked and exact-link counts, missing evidence, restart-safe reads and no-actionable capability.
- [x] Implement a local read-only freshness and lineage-coverage aggregation service without creating, changing or resolving any evidence record or downstream gate.
- [x] Expose a display-safe evidence freshness and lineage-coverage dashboard in the workbench without approval, promotion, order, paper-run, broker, feed, scheduler or execution controls.
- [x] Document dashboard semantics, counting/freshness limits, fixture/manual-declaration limitations and strict no-live exclusions.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option O changes to `main`, then report completion and request the next separate approval.

## Option P — read-only retained-evidence export manifest

- [x] Audit retained experiment artifacts, robustness, paper-run, dataset-review, linkage and export interfaces for a bounded deterministic manifest seam.
- [x] Define failing deterministic acceptance tests for selected retained evidence, canonical stable serialization/hash, missing/mismatched evidence conditions, secret exclusion, restart-safe reads and no-actionable capability.
- [x] Implement a local read-only manifest service that assembles selected retained evidence IDs, policies, timestamps, blockers, lineage and content hash without writing, fetching or changing a gate.
- [x] Expose a display-safe manifest preview and local download in the workbench without promotion, approval, order, paper-run, broker, feed, timed work or execution controls.
- [x] Document manifest contents, deterministic/hash semantics, secret exclusions, fixture/manual-declaration limitations and strict no-live exclusions.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option P changes to `main`, then report completion and request the next separate approval.

## Option Q — read-only retained-manifest comparison

- [x] Audit the Option P manifest contract, canonical hash, selected-evidence composition and Reporting export seams for a deterministic comparison view.
- [x] Define failing deterministic acceptance tests for identical manifests, named lineage/policy/parameter/timestamp/blocker/hash differences, secret exclusion, stable ordering and no-actionable capability.
- [x] Implement a local read-only manifest comparison service that compares two selected retained manifest payloads without writing, merging, ranking, fetching or changing any gate.
- [x] Expose a display-safe manifest comparison view in the workbench without promotion, approval, order, paper-run, broker, feed, timed work or execution controls.
- [x] Document comparison semantics, difference ordering, hash/secret limitations, fixture/manual-declaration limitations and strict no-live exclusions.
- [x] Run lint, full tests, compilation, whitespace, safety scans and browser validation.
- [x] Commit and push only Option Q changes to `main`, then report completion and request the next separate approval.

## Repository cleanup and research-workbench refinement

- [x] Inventory repository files, documentation, developer artifacts and local workbench copy to identify only confirmed obsolete, duplicated, or irrelevant cleanup candidates.
- [x] Classify each candidate as retain, consolidate, reword, or remove; preserve required architecture, evidence lineage, safety disclosures, test fixtures, interfaces, and service wiring.
- [x] Remove only confirmed non-required clutter and consolidate any redundant project documentation without deleting current architecture or operation guidance.
- [x] Refine the local workbench into a cleaner research-oriented presentation, reducing repetitive early-stage terminology while retaining honest sample-data and no-live disclosures at relevant interaction points.
- [x] Add or adjust deterministic tests where UI/public copy or cleanup can affect contract expectations; do not weaken safety or fixture-honesty coverage.
- [x] Run lint, full tests, whitespace, repository-reference, secret, prohibited-capability, and fresh-browser checks.
- [x] Commit and push only the conservative cleanup changes to `main`, then report the retained/removed/reworded inventory and ask approval before a separate next slice.

## Post-audit build-closure plan

- [ ] Priority 1: decompose the large Streamlit workbench into page-level renderers and wiring helpers without changing application-service contracts, data semantics, safety copy, or active navigation.
- [ ] Priority 2: refine retained research and artifact inspection UX through application-service reads only; preserve honest provenance, no-live, no-recommendation, and no-authority boundaries.
- [ ] Priority 3: design and acceptance-test the manual, bounded Angel historical-data gate covering canonical instrument selection, research-use enforcement, interval/window limits, source/refresh validation, immutable retention, and named failures; do not implement new provider actions in this slice.
- [ ] Priority 4: only after separate approval and user-owned local configuration, implement the bounded historical-data retrieval vertical slice with no live quotes, WebSockets, account/position access, order endpoints, scheduler, or cloud deployment.
- [ ] Priority 5: define the longer local paper-observation evidence gate before considering any broker-authoritative marks or reconciliation; no live execution is implied.
- [ ] Keep cloud deployment and controlled live execution as separate future decisions requiring independent security, data-rights, operational, broker/member, and legal review; never infer them from a dashboard or backtest result.
- [ ] Approve exactly one priority before implementation and close it with focused tests, full verification, browser validation where applicable, and a clean pushed commit.

This checklist is a build plan only; it does not authorize live trading, cloud deployment, background automation, broker order access, or customer-facing financial claims.
