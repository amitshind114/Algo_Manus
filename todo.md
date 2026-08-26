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
