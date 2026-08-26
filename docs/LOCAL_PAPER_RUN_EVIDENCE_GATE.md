# Local Paper-Run Evidence Gate

## Purpose and non-authorization boundary

Option L adds a **local evidence-completeness assessment** before a user considers an existing simulated paper workflow. It records whether named retained references are present and within a declared local age policy. It is deliberately separate from research promotion, proposal-level risk, paper-event lifecycle handling, and all execution capability.

> `EVIDENCE_COMPLETE` means only that the specific retained records named in the assessment were available and met the configured local age limits at the recorded assessment time. It does **not** approve a paper run, authorize an order, select a strategy, certify a dataset, predict performance, or relax any existing gate.

| Evidence input | Assessment reads | Assessment does not do |
|---|---|---|
| Research promotion evidence | Existing batch, immutable research manifest, and accepted validation outcome through the current read-only resolver | Create, amend, promote, or approve research evidence |
| Robustness evidence | Existing immutable robustness record that matches dataset ID, strategy ID/version, and candidate parameter-revision ID | Rank candidates, accept performance, infer suitability, or rerun a backtest |
| Risk-control evidence | Existing durable central-policy version and current kill-switch change | Evaluate a proposal, calculate portfolio risk, change a control, or override a kill switch |
| Paper operations | Nothing is appended to the paper ledger | Propose, accept, submit, work, fill, cancel, reconcile, or route an order |

## Deterministic assessment policy

The recorded `PaperRunEligibilityPolicy` has a version plus positive maximum ages for research and robustness evidence. The assessment time is explicit. Research freshness is measured from the retained manifest’s information cutoff, while robustness freshness is measured from the robustness record’s retained creation time. A source is stale only when its age is greater than the declared maximum; future-dated evidence is not silently marked stale.

The policy assessment reads promotion evidence first. If it resolves, the service requires matching robustness evidence for the exact dataset, strategy/version, and parameter-revision lineage. Matching refers to retained identities, never to P&L, return, trade count, or a preferred candidate. It then reads the current passed-in durable risk-control snapshot and records its central-policy version and kill-switch change ID.

| Result state | Interpretation |
|---|---|
| `EVIDENCE_COMPLETE` | Promotion evidence resolved, matching robustness evidence exists and is not insufficient-history/stale under the stated policy, and the retained kill switch is inactive. This remains evidence-only. |
| `BLOCKED` | One or more retained references is missing, mismatched, insufficient, stale, or the durable kill switch is active. No fallback or partial approval occurs. |

## Named blockers

The record retains zero or more deterministic named reasons. A blocked row can carry several reasons because the service reports all independently observable deficiencies rather than selecting a winner.

| Blocking reason | Exact condition |
|---|---|
| `RESEARCH_PROMOTION_EVIDENCE_MISSING` | No persisted batch/manifest/accepted validation evidence resolves for the requested batch and instrument. |
| `RESEARCH_EVIDENCE_STALE` | The research manifest information cutoff exceeds the policy’s permitted age at assessment time. |
| `ROBUSTNESS_EVIDENCE_MISSING` | No retained robustness record has the requested dataset and strategy lineage. |
| `ROBUSTNESS_PARAMETER_REVISION_MISMATCH` | A retained robustness record matches dataset and strategy lineage but has no candidate with the experiment’s parameter-revision ID. |
| `ROBUSTNESS_HISTORY_INSUFFICIENT` | The matching retained robustness record explicitly reports insufficient partition history. |
| `ROBUSTNESS_EVIDENCE_STALE` | The matching robustness record exceeds the policy’s permitted age at assessment time. |
| `KILL_SWITCH_ACTIVE` | The passed-in durable risk-control snapshot has an active kill-switch change. |

## Immutable local retention

Each assessment is stored in local `paper_run_eligibility.sqlite3` under `ALGO_MANUS_DATA_DIR` (default `~/.algo-manus`). The immutable evidence identity includes the batch/instrument, resolved source identities, policy/version and age limits, risk-control references, blockers, and explicit assessment time. Saving the exact same record is idempotent; a different payload under the same identity fails explicitly.

| Retained context | Examples |
|---|---|
| Research lineage | Batch ID, manifest ID, dataset ID, strategy ID/version, parameter-revision ID |
| Robustness lineage | Robustness evidence ID only when an exact candidate-revision match exists |
| Control lineage | Eligibility-policy version, central-policy version, durable kill-switch change ID |
| Assessment result | State, full ordered blocker list, timezone-aware assessment time |

The record is local operational evidence, not a signature, trusted timestamp, broker confirmation, cloud backup, market-data certificate, audit opinion, or proof of current eligibility outside this program’s declared local scope.

## Workbench and existing gates

The **Risk & paper** page provides an evidence-assessment panel with an explicit retained research instrument context and an action labelled **Record local evidence assessment**. This action only writes the immutable assessment record. It cannot initiate a paper run, approve a proposal, switch a strategy, change promotion status, alter controls, submit an order, or add any paper ledger event.

The existing read-only `PaperResearchPromotionService` remains the source for persisted manifest and accepted validation evidence. The existing deterministic central risk engine remains the sole proposal-level control in the paper simulator. It must independently evaluate the full order, portfolio, limits, current risk-control snapshot, instrument status, and retained promotion evidence. The Option L record cannot be passed as a replacement for promotion evidence and does not change paper-event state transitions.

## Data and research limitations

Fixture datasets are deterministic workflow samples, not broker data, market evidence, performance records, or recommendations. Retained historical datasets can still be stale, incomplete, affected by corporate actions, subject to survivorship/instrument changes, or unsuitable for a question. A matching robustness record is not a proof against overfitting, selection bias, regime change, liquidity constraints, transaction-cost error, or future loss.

Option L adds no broker account/profile/funds/RMS/holdings/positions capability, LTP/live price, live feed, WebSocket, data retrieval, order/cancellation endpoint, paper broker, scheduler, worker, external queue, cloud deployment, autonomous execution, or recommendation capability.

This is research and analysis only, not personalized financial advice.
