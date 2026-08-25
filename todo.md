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
