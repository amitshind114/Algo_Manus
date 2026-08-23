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

## Read-only integrity interpretation

| Status | Meaning |
|---|---|
| `VALID` | The retained payload has the expected local shape and the event fits the local lifecycle sequence observed by the reader. |
| `MALFORMED_PAYLOAD` | The retained payload cannot be parsed as the expected local canonical payload shape. |
| `INVALID_LIFECYCLE` | The retained event does not fit the local lifecycle sequence observed by the reader. |
| `MALFORMED_PAYLOAD_AND_INVALID_LIFECYCLE` | Both conditions apply to the same retained event. |

The workbench displays total retained events, valid interpretations, malformed payloads and invalid lifecycle transitions for the selected scope. Malformed-payload and invalid-lifecycle totals may overlap when one event has both conditions. These fields only describe the current local reader interpretation; they never repair, remove, amend, reconcile, or confirm the retained events.

## Optional integrity scope

The workbench may display all retained events, only `VALID` local interpretations, or only local integrity issues. The issue-only scope includes every non-`VALID` status, including events with both a malformed payload and invalid lifecycle. A blank or unknown integrity filter is rejected by the application read service. Integrity scope changes only the displayed retained local rows and totals; it does not repair, alter, export, synchronize or confirm events.

## Optional retained event-type scope

The workbench may display all retained local event types or one type: `RISK_DECISION`, `ORDER_SUBMITTED`, `ORDER_FILLED`, `ORDER_CANCELLED`, or `ORDER_REJECTED`. A blank or unknown event-type filter is rejected by the application read service. Event-type scope combines with retained-order and integrity scopes only to narrow displayed local rows and totals; it does not alter the local ledger, lifecycle, risk controls, promotion evidence, or any execution state.

## Optional retained instrument scope

The workbench may display all retained local instruments or one retained canonical instrument ID. A blank or unknown instrument filter is rejected by the application read service. Instrument scope combines with retained-order, integrity and event-type scopes only to narrow displayed local rows and totals; it does not alter the local ledger, lifecycle, risk controls, promotion evidence, or any execution state.

## Optional retained event-time window

The workbench may display all retained local events or an inclusive UTC start/end window based on each event's retained occurrence time. Both application-service bounds must be timezone-aware, and a start bound after the end bound is rejected. The local UI labels its date and time controls as UTC and does not call the reader for an inverted window. Time-window scope combines with retained-order, integrity, event-type and instrument scopes only to narrow displayed local rows and totals; it does not alter the local ledger, lifecycle, risk controls, promotion evidence, or any execution state.

## Active-filter summary

The application read service can return an immutable local summary of the active retained order, integrity, event-type, instrument and UTC time-window scopes. `ALL` denotes an unrestricted dimension, while UTC start/end values are retained exactly as the validated inclusive bounds. The workbench displays this summary only for a valid scope set. It is not an export, broker request, execution instruction, reconciliation result, or repair record.

## Local scope presets

The application read service exposes immutable local presets for `ALL`, `VALID`, and `ISSUES` integrity interpretation scopes. The workbench's preset selector applies only that integrity dimension; retained order, event-type, instrument and UTC time-window controls remain independent. Selecting **Manual integrity filter** instead exposes the existing manual integrity selector. Unknown preset identities are rejected, and a preset never writes, repairs, reconciles, exports, synchronizes or confirms retained events.

## Retained audit-row detail

The application read service can resolve one retained local event by its event ID into an immutable pair of the interpreted audit row and its original serialized local payload. The workbench offers this detail selector only when the currently displayed local scope contains rows. Blank or unknown event IDs are rejected. A malformed payload remains visible as retained text and is marked through the existing payload-valid and integrity interpretation fields; row detail never repairs, changes, exports, reconciles, synchronizes or confirms an event.

## Retained payload-side scope

The application read service can restrict displayed audit rows to already-interpreted retained payload sides: `ALL`, `BUY`, or `SELL`. Rows without a retained valid side do not match a buy or sell scope. Blank and unknown side values are rejected. The workbench displays this scope separately from order, integrity, event-type, instrument and UTC time-window controls. It only filters the local audit display; it never writes, repairs, reconciles, exports, synchronizes or executes any event.

## Limits

Timeline state is derived from the current retained ledger sequence. It is not broker acknowledgement, account reconciliation, venue execution confirmation, market-data evidence, price validation, or a trading recommendation. A valid local payload does not prove external execution.

The timeline has no submit, cancel, amend, reconcile, export, synchronization, provider, credential, broker, cloud, scheduler or live-execution authority.

This is research and analysis only, not personalized financial advice.
