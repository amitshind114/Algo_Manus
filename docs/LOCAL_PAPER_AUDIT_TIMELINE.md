# Local Paper-Operation Audit Timeline

## Scope

Phase 8A adds a read-only chronological view of retained events from the local append-only paper ledger. Each row represents one already-stored local fixture event. The timeline does not create, repair, replay into a new ledger, alter promotion status, or perform any execution action.

## Retained audit fields

| Field | Meaning |
|---|---|
| Time and event | The retained event timestamp and local event type. |
| Lifecycle state | The state reached by applying the retained event to the existing local lifecycle transition rule. `UNPROJECTABLE` means the stored sequence cannot be interpreted as a valid local transition. |
| Order and instrument | The retained local order ID and instrument identity. |
| Side, quantity, reference price and fill price | Values only when present in that event’s retained local payload. An absent value is displayed as `—`; no value is inferred or fetched. |
| Decision and central gate | Retained risk-decision code and central decision type when present. |
| Research identifiers | Retained promotion-evidence batch, manifest, dataset and validation-policy identifiers when present on the risk-decision event. |
| Payload valid | Whether the stored event payload has the expected local canonical payload shape. |

## Optional retained-order scope

The workbench may display all retained local audit rows or rows for one selected retained local order ID. Selecting an order changes only the rows displayed. A blank or unknown order ID is rejected by the application read service; neither case changes the local ledger, risk controls, promotion evidence or projected portfolio state.

## Limits

Timeline state is derived from the current retained ledger sequence. It is not broker acknowledgement, account reconciliation, venue execution confirmation, market-data evidence, price validation, or a trading recommendation. A valid local payload does not prove external execution.

The timeline has no submit, cancel, amend, reconcile, export, synchronization, provider, credential, broker, cloud, scheduler or live-execution authority.

This is research and analysis only, not personalized financial advice.
