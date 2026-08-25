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
