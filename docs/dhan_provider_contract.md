# Dhan Historical Data Provider Contract

Status: DRAFT - IMPLEMENTATION BLOCKED

This contract must be fully confirmed from current official Dhan documentation before the historical-data adapter is implemented.

## Required fields

| Field | Status | Confirmed value | Source |
|---|---|---|---|
| API base URL | UNCONFIRMED |  |  |
| API version | UNCONFIRMED |  |  |
| Historical candles endpoint | UNCONFIRMED |  |  |
| HTTP method | UNCONFIRMED |  |  |
| Authentication header | UNCONFIRMED |  |  |
| Client identifier requirement | UNCONFIRMED |  |  |
| Token lifetime | UNCONFIRMED |  |  |
| Token refresh behavior | UNCONFIRMED |  |  |
| Security ID field | UNCONFIRMED |  |  |
| Exchange segment field | UNCONFIRMED |  |  |
| Supported intervals | UNCONFIRMED |  |  |
| Maximum request window per interval | UNCONFIRMED |  |  |
| Pagination or chunking behavior | UNCONFIRMED |  |  |
| Timestamp timezone | UNCONFIRMED |  |  |
| Candle timestamp semantics | UNCONFIRMED |  |  |
| OHLCV response fields | UNCONFIRMED |  |  |
| Missing volume policy | UNCONFIRMED |  |  |
| Error and status-code contract | UNCONFIRMED |  |  |
| Rate limits | UNCONFIRMED |  |  |
| Data entitlement and permitted use | UNCONFIRMED |  |  |
| Corporate-action adjustment basis | UNCONFIRMED |  |  |
| Historical coverage and retention | UNCONFIRMED |  |  |
| Static IP requirement for historical endpoint | UNCONFIRMED |  |  |

## Implementation rule

No Dhan historical-data adapter may be enabled while any required field remains `UNCONFIRMED`.

The adapter must fail closed when the provider contract is incomplete.
