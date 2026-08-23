# Local Evidence Health Scope Comparison

## Scope

Phase 7F compares the current local artifact-health status counts of two distinct retained experiment batches. It uses the existing read-only single-batch scope path and presents left count, right count, and the exact absolute count delta of **right minus left**.

## Count semantics

| Count | Meaning |
|---|---|
| Results | Current retained result rows in that batch. |
| Complete / unavailable / incomplete / result-spec mismatch | Current local structural health counts under the established integrity rules. |
| Needs attention | Current total of non-complete local results. |
| Right − left | The exact right-side count minus the left-side count; a negative value means the right retained batch has fewer of that status. |

The comparison service requires two known and distinct retained batch IDs. It rejects an unknown ID or the same ID on both sides. The workbench prevents same-batch selection by removing the selected left batch from right-batch options.

## Limits

This comparison is a current local fixture-evidence count comparison only. It is not a performance comparison, market-data comparison, broker comparison, data-quality verdict, execution check, recommendation, or causal audit. It has no authority to mutate, repair, regenerate, delete, export, synchronize, promote, submit, schedule or connect to an external service.

No broker SDK, provider/network call, credential, cloud connection, real paper-broker link or live-execution capability is included.

This is research and analysis only, not personalized financial advice.
