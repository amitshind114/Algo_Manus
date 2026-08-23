# Local Research Terminal UI/UX Specification

## Product intent

Algo Manus is a **calm, information-dense desktop research terminal** for local research and paper operations. It must help a user trace an instrument, data source, strategy configuration, reproducible result, risk decision and paper event without confusing fixture output for market evidence or treating a dashboard as execution authority.

The local Streamlit interface remains a presentation layer. Every displayed operational value comes from an application read model or is visibly labelled as fixture/demonstration state.

## Visual system

| Principle | Requirement |
|---|---|
| Theme | Dark-first professional terminal with an accessible light option; neutral charcoal/navy surfaces, restrained blue information accents. |
| Semantic status | Green only for confirmed healthy/positive states; red only for loss/error/rejection; amber for stale/warning/paper attention; blue/gray for neutral context. Every color state also has text or icon/label. |
| Density | Desktop-first, fixed left navigation, compact metric rows, tables with column controls, panels ordered by decision flow rather than decorative card grids. |
| Typography | Clear tabular numerics; monospaced treatment for IDs, hashes and timestamps; labels use sentence case and avoid promotional language. |
| Numbers | Show currency (`₹` where applicable), unit, timeframe, source/mode and timestamp where meaningful. Blank or unavailable data must be named, not rendered as zero. |
| Motion | Minimal and functional. Navigation and reveal transitions may be short; no distracting market-style animations or decorative gradients. |

## Global frame

### Persistent sidebar

The left panel remains visible on desktop and shows: product identity; current mode; active data/source status; the navigation below; concise research/paper indicators; and an unambiguous global kill-switch indicator when paper capability exists. It never shows a secret, account credential or broker token.

### Global mode banner

Every primary workspace presents a compact, persistent mode/source banner.

| Mode | Banner content |
|---|---|
| `DEMO` | “Fixture mode — deterministic local sample data. Not broker or market data.” |
| `RESEARCH` | Data source, dataset/snapshot ID, interval, range, retrieval time and freshness status. |
| `PAPER` | “Paper mode — simulated execution only,” policy version, mark source/freshness and kill-switch status. |
| `LIVE` | Not rendered until a separately approved implementation exists; a future design must distinguish it visually and require explicit human activation. |

## Primary navigation

The existing fixed-navigation workbench is retained as the starting point. It grows into these ten service-backed areas.

| Navigation area | Primary purpose | Required state and evidence |
|---|---|---|
| **Overview** | Start from current mode, health and recent activity. | Mode, system health, data freshness, active risk/kill state, latest runs/errors and explicit no-data state. |
| **Instruments & Data** | Search validated instruments and inspect provenance. | Identity, exchange/segment, active flag, expiry/strike/option type/lot/tick when supported, source/freshness/validation warnings. |
| **Strategy Lab** | Select a registered strategy and validate a configuration. | Metadata/version/risk notes, schema-driven form, compatibility validation, named configuration read model and explicit “Run Backtest” action only. |
| **Backtests** | Inspect one immutable run and artifacts. | Manifest, equity/drawdown curves, metrics/definitions, assumptions, trade and rejected-event ledger, export links. |
| **Experiments** | Compare immutable research results across selected universes. | Filters, transparent metric definitions, leaderboard, reproducibility panel and visible result status. |
| **Paper Trading** | Review a paper proposal through policy and lifecycle. | Paper banner, proposal, risk decision/reason, order state, fills/open orders/positions and source freshness. |
| **Portfolio & Risk** | Inspect event-derived portfolio and policy utilization. | Positions, realised/unrealised P&L, exposure, limits/utilization, daily loss/drawdown, kill state and risk-event timeline. |
| **Orders & Audit** | Search immutable order, fill and audit evidence. | Filterable tables with correlation/run/strategy/instrument/status/time; exact timestamps and rejection reason codes. |
| **Operations** | Diagnose local runtime/data/storage state. | Database/migration status, last successful operation, errors, backup/export action with confirmation and recovery guidance. |
| **Settings** | View non-secret local configuration and policy references. | Current mode policy, storage location indicator, UI theme and non-sensitive defaults; never raw credentials. |

## Screen behavior

### Overview

Overview contains no performance marketing. It is a command center with a concise mode banner, source/data freshness, health summary, active experiment/paper state and a chronological event/error list. Empty state must say what is missing and link to the next valid workflow step.

### Instruments & Data

Search is always bound to the current validated instrument snapshot, not a hand-maintained ticker list. Table columns adapt by instrument type but never invent derivatives data. The current fixture browser remains clearly labelled until an approved instrument master exists. A future sync action is unavailable unless the approved provider adapter and confirmation workflow exist.

### Strategy Lab and Backtests

The strategy catalog lists **only registered implementations**. Planned strategies must not be positioned as selectable production features. Parameter forms use the registry schema and provide inline errors before a request is submitted to the application service. A run opens a read-only manifest plus clear metrics, assumptions, curves and trade/rejected-event evidence.

### Experiments

The leaderboard is a comparison surface, not a profitability claim. Each row exposes its strategy revision, dataset/snapshot, cost assumptions, time window and result status. Sort direction and metric definitions are explicit. Missing profit factor, absence of trades or insufficient history are shown as unavailable/not applicable—not forced into misleading values.

### Paper Trading, Portfolio & Risk

Paper proposal, risk decision, order lifecycle and fill projection appear in time order. A visible `PAPER MODE` banner and kill-switch state are permanent. The UI must never present a “buy”/“sell” action that bypasses the central risk engine. Portfolio values only appear after the relevant event projection exists; they do not use UI session state as a source of truth.

### Orders, Audit and Operations

Tables support filters but preserve immutable records and exact reason codes. Operations reports system state rather than internal stack traces or secrets. Backup/export always requires confirmation and reports a non-sensitive outcome. Empty audit tables, stale data, unsupported features and blocked modes use intentional content—not blank panels.

## Component and state rules

| Rule | Requirement |
|---|---|
| Reuse | Extract banner, metric strip, provenance panel, data table, manifest panel, status badge and empty/error states into view helpers/components. |
| Service boundary | UI invokes application commands/queries only and renders typed result objects. |
| Data truthfulness | Fixtures, delayed data, historical data, paper marks and live data each receive distinct visible labels. |
| Accessibility | Keyboard-reachable navigation, descriptive labels, non-color status cues, readable contrast and responsive table overflow. |
| Error behavior | Catch/display typed application errors; include recoverable next step without hiding error code/correlation ID where safe. |
| Empty behavior | State why data is absent, what prerequisites exist and which approved workflow can populate it. |

## Current-to-target transition

| Existing workbench screen | Target evolution | Prerequisite |
|---|---|---|
| Home | Overview with persisted health, freshness and recent activity. | Operations read model. |
| Data & instruments | Add source/validation/derivatives fields from canonical snapshot. | Instrument/data contracts and approved source only. |
| Backtesting | Split configuration and immutable run inspection. | Strategy registry and run manifest. |
| Multi-test leaderboard | Become Experiments with filters and reproducibility drawer. | Persisted experiment query service. |
| Strategies | Become schema-driven Strategy Lab. | Registry and parameter validation. |
| Reporting | Merge into Backtests/Experiments artifact panels. | Rich metrics/artifact repositories. |
| Risk & paper | Split Paper Trading and Portfolio & Risk. | Risk engine, projection and lifecycle state machine. |
| Roadmap | Retain as Operations/readiness context or documentation link. | No runtime prerequisite. |

## Explicit exclusions

This specification does not add brokerage credentials, live instruments, market feed polling, automatic orders, recommendations, financial advice or a cloud runtime. It defines how those capabilities would be displayed only after their underlying contracts, controls, evidence and approvals are completed.

## References

[1]: ./ARCHITECTURE_GAP_ASSESSMENT.md "Architecture gap assessment"
[2]: ./TARGET_ARCHITECTURE.md "Target architecture"
[3]: ../src/algo_manus/ui/workbench.py "Current local workbench"
