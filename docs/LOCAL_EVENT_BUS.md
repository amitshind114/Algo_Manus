# Local In-Process Event Bus

## Purpose and boundary

Option G introduces a small **in-process local event boundary** for wiring already-retained research and paper evidence to local subscribers and a read-only audit surface. It is intentionally not an event broker, queue, scheduler, streaming service, webhook, background worker, or durable event store.

> The source evidence remains authoritative: research manifests/experiment batches and paper-ledger events are retained by their existing local SQLite stores. The event bus only records a bounded current-process trace that points back to that source evidence.

## Published local event types

| Local event type | Publication point | Required retained source evidence | Correlation ID |
| --- | --- | --- | --- |
| `RESEARCH_BATCH_RETAINED` | After the research manifest and experiment batch have been saved. | Research manifest ID and experiment batch ID. | Experiment batch ID. |
| `PAPER_LEDGER_EVENT_RETAINED` | After the immutable `PaperEvent` has been appended to the local paper ledger. | Paper event ID, paper lifecycle event type, and instrument ID. | Paper order ID. |

The paper publisher follows the canonical Option E ordering. For an allowed local paper proposal, the source paper ledger retains and the bus publishes references to `ORDER_PROPOSED`, then `RISK_DECISION`, then `ORDER_ACCEPTED`. If a source write fails, no corresponding local bus event can be published.

## Dispatch semantics

| Property | Implemented behavior | Limitation |
| --- | --- | --- |
| Event identity | A deterministic SHA-256-derived event ID covers type, timestamp, correlation, producer and scalar attributes. | Identical current-process events are suppressed; this is not a cross-process idempotency store. |
| Event payload | Immutable scalar attributes, including `source_evidence_id`; mappings are made read-only. | The bus never copies complete research or paper payloads and is not a source-of-truth archive. |
| Order | Publication order is retained in the current process. | There is no distributed ordering, partitioning or transaction coordinator. |
| Subscribers | Registered synchronously with a stable local name. | There is no async consumer, retry queue, dead-letter queue, worker, rate control or delivery guarantee beyond the current call. |
| Failure isolation | A subscriber exception is captured as a `FAILED` delivery row and does not block later subscribers or roll back already-retained source evidence. | Failed rows are local diagnostics, not a retry/recovery mechanism. |
| Retention | The event and delivery trace is bounded in memory. | It is deliberately empty on application/process restart. |

## Read-only wiring audit

The **Risk & paper** page includes a read-only current-process wiring audit. It shows the local event type, correlation ID, producer, durable source-evidence ID, and subscriber delivery/failure counts. Its summary explicitly reports that the bus is non-durable, bounded and empty after restart.

This view cannot publish, subscribe, replay, repair, synchronize, reconfigure or act on an event. It does not provide broker routing, portfolio updates, scheduler control, alerting, account access, reconciliation proof, or live execution.

## Explicit exclusions

Option G adds no external queue or broker such as Kafka, RabbitMQ, Redis Streams, SQS, Pub/Sub or NATS; no HTTP client, WebSocket, webhook, message consumer, thread, task runner, scheduler, long-running service, cloud deployment, broker endpoint, price feed, account endpoint, paper broker, or live order path.

If a future approved architecture needs durable or distributed event infrastructure, it must define its own outbox/transaction boundary, schema versioning, retention, consumer idempotency, authentication, encryption, monitoring, failure recovery, incident process and separate live-readiness review. That work is not implied or started by this local slice.

This is research and analysis only, not personalized financial advice.
