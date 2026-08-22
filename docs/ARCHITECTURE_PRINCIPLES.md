# Architecture Principles

## System boundaries

The architecture separates six trust zones: data acquisition, research/analytics, deterministic risk policy, paper execution, future live execution and user-facing operations. These zones communicate through canonical typed contracts and durable events. No component receives authority simply because it can calculate, summarize or display a market view.

```text
Approved data sources
        │
        ▼
Data lineage + instrument/session registry
        │
        ├──────────────► Research and backtest experiments ──► Non-executable proposal
        │                                                           │
        ▼                                                           ▼
Portfolio/exposure state ◄── Reconciled events ◄── Paper execution ◄── Deterministic risk policy
                                                                         │
                                                                         └──► Future live boundary (separately approved)
```

## India-market model

India-market support means the domain model understands cash-equity and listed-derivative sessions, venue/segment identifiers, holiday and expiry calendars, instrument/contract versions, trading symbols, lot sizes, tick sizes, product/margin categories and corporate-action adjustments. These concepts will be sourced from versioned data services rather than constants embedded in strategy or user-interface code.

## Event and reconciliation model

Positions and P&L are projections of reconciled events. The model must distinguish a human or system proposal, risk approval, order intent, broker submission, broker acceptance, exchange acknowledgement, partial fill, full fill, cancellation, rejection and reconciliation correction. Every event carries event time, received time, source, correlation ID, causation ID and immutable payload version.

## Deterministic risk boundary

The risk service evaluates only authoritative state and deterministic policy. It must validate session state, instrument tradability, lot/tick constraints, data freshness, policy limits, available resources, aggregate exposure and per-leg strategy constraints. It can approve, reduce, defer or reject an order intent, with its decision and inputs retained as audit evidence.

Research, UI and LLM components may request a policy evaluation. They cannot write an approval, bypass a rejection or mutate the authoritative position state.

## AI boundary

LLMs may assist with research summarization, issue detection and proposal drafting. They are not market-data authorities, risk engines or execution controllers. Any LLM-derived statement must be linked to timestamped evidence and is considered non-executable until it passes deterministic validation and any required human review.

## Future multi-asset extension

The canonical model is venue-extensible but not venue-agnostic by omission. Future FX and crypto modules will explicitly implement their own market sessions, funding/roll conventions, custody/margin/liquidation models, contract types and regulatory controls. India-market defaults may not cross this boundary.

This is research and analysis only, not personalized financial advice.
