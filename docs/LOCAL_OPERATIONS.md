# Local Operational Controls

The current build supports **research** and **paper** runtime modes only. It writes append-only local audit records, redacts credential-like fields before persistence and reports health status for the local data directory and explicitly blocked broker/live capabilities.

The health projection is intentionally conservative. A healthy local directory does not mean data is current, a backtest is valid, paper results are suitable for production or a broker integration is ready. Those remain separate checks in later approved gates.

The repository contains no scheduler, background worker, cloud process, broker credential, TOTP handler, order router or live-order code. Any future recurring master/data refresh must be configured as an explicit local service after an approved provider integration and operational review.

This is research and analysis only, not personalized financial advice.
