# Dhan Historical Data Provider Contract

Status: CONFIRMED - PHASE 1 COMPLETE

Contract confirmed from the official DhanHQ v2 Historical Data documentation and DhanHQ Annexure.

Sources:

- https://dhanhq.co/docs/v2/historical-data/
- https://dhanhq.co/docs/v2/instruments/
- https://dhanhq.co/docs/v2/annexure/
- https://dhan.co/support/platforms/dhanhq-api/what-are-the-api-rate-limits-for-dhan/

## Confirmed contract

| Field | Status | Confirmed value | Source |
|---|---|---|---|
| API base URL | CONFIRMED | `https://api.dhan.co/v2` | DhanHQ v2 Historical Data documentation |
| Public instrument-master source | CONFIRMED | `https://images.dhan.co/api-data/api-scrip-master-detailed.csv` | DhanHQ v2 Instruments documentation |
| Public instrument-master format | CONFIRMED | Detailed UTF-8 CSV with exchange, segment, security ID, instrument, expiry, strike, option, lot and tick fields | DhanHQ v2 Instruments documentation |
| API version | CONFIRMED | v2 | DhanHQ v2 Historical Data documentation |
| Daily candles endpoint | CONFIRMED | `POST /charts/historical` | DhanHQ v2 Historical Data documentation |
| Intraday candles endpoint | CONFIRMED | `POST /charts/intraday` | DhanHQ v2 Historical Data documentation |
| HTTP method | CONFIRMED | POST | DhanHQ v2 Historical Data documentation |
| Authentication header | CONFIRMED | `access-token: <JWT access token>` | DhanHQ v2 Historical Data documentation |
| Client identifier requirement | CONFIRMED | Not required for historical-data request headers; use the access token | DhanHQ v2 Historical Data documentation |
| Token lifetime | CONFIRMED | Access-token lifetime is account/provider-specific; adapter must not implement refresh | DhanHQ releases and support documentation |
| Token refresh behavior | CONFIRMED | No automatic refresh in Algo Manus; fail closed on authentication failure | Algo Manus safety boundary |
| Security ID field | CONFIRMED | `securityId` | DhanHQ v2 Historical Data documentation |
| Exchange segment field | CONFIRMED | `exchangeSegment` using Dhan segment enum | DhanHQ v2 Annexure |
| Intraday instrument field | CONFIRMED | `instrument: EQUITY` for supported equity segments; unsupported mappings fail closed | DhanHQ v2 Historical Data documentation; Algo Manus adapter policy |
| Open-interest field | CONFIRMED | `oi: false` for the current equity-only adapter | DhanHQ v2 Historical Data documentation; Algo Manus adapter policy |
| Supported exchange segments | CONFIRMED | `IDX_I`, `NSE_EQ`, `NSE_FNO`, `NSE_CURRENCY`, `BSE_EQ`, `MCX_COMM`, `BSE_CURRENCY`, `BSE_FNO` | DhanHQ v2 Annexure |
| Supported daily intervals | CONFIRMED | Daily only | DhanHQ v2 Historical Data documentation |
| Supported intraday intervals | CONFIRMED | 1, 5, 15, 25, and 60 minutes | DhanHQ v2 Historical Data documentation |
| Maximum intraday request window | CONFIRMED | 90 days per request | DhanHQ v2 Historical Data documentation |
| Daily request bounds | CONFIRMED | `fromDate` inclusive; `toDate` non-inclusive; format `YYYY-MM-DD` | DhanHQ v2 Historical Data documentation |
| Intraday request bounds | CONFIRMED | `fromDate` and `toDate`; IST datetime format such as `YYYY-MM-DD HH:MM:SS` | DhanHQ v2 Historical Data documentation |
| Pagination or chunking behavior | CONFIRMED | No documented pagination; Algo Manus splits one explicit retrieval into sequential non-overlapping 90-day requests | DhanHQ v2 Historical Data documentation; Algo Manus adapter policy |
| Timestamp timezone | CONFIRMED | Unix epoch seconds | DhanHQ v2 Historical Data documentation |
| Candle timestamp semantics | CONFIRMED | Provider returns epoch-second timestamps; adapter converts to timezone-aware UTC and preserves provider timestamps | DhanHQ v2 Historical Data documentation |
| OHLCV response fields | CONFIRMED | Parallel arrays: `open`, `high`, `low`, `close`, `volume`, `timestamp`; optional `open_interest` | DhanHQ v2 Historical Data documentation |
| Missing volume policy | CONFIRMED | Missing or invalid volume must be rejected; adapter must not invent a default volume | Algo Manus data-quality policy |
| Error and status-code contract | CONFIRMED | `DH-904` rate limit, `DH-905` input error, `DH-907` data error; data codes include `805`, `806`, `807`, `808`, `812`, `813` | DhanHQ v2 Annexure |
| Rate limits | CONFIRMED | Data APIs: up to 5 requests per second | Dhan support documentation |
| Data entitlement and permitted use | CONFIRMED | User must hold required Dhan data entitlement; Algo Manus uses data for local research and backtesting only | User/account responsibility |
| Corporate-action adjustment basis | CONFIRMED | Not documented as adjusted; adapter must label data as unadjusted/unknown and must not apply silent adjustments | DhanHQ v2 Historical Data documentation |
| Historical coverage and retention | CONFIRMED | Daily data available from instrument inception; intraday data available for the last 5 years | DhanHQ v2 Historical Data documentation |
| Static IP requirement for historical endpoint | CONFIRMED | Not documented for historical data; do not assume order-API static-IP requirements apply | DhanHQ v2 Historical Data documentation |

## Adapter implementation rules

1. Use `POST /charts/historical` for daily candles.
2. Use `POST /charts/intraday` for 1, 5, 15, 25, and 60-minute candles.
3. Send the Dhan JWT in the `access-token` header.
4. Map canonical Algo Manus instruments to Dhan `securityId` and `exchangeSegment` through an accepted local instrument snapshot.
5. Accept up to five years of intraday history, splitting each explicit retrieval into sequential non-overlapping 90-day requests.
6. Send `instrument: EQUITY` and `oi: false` for supported equity segments; fail closed for unsupported derivative, currency, commodity, and index mappings.
7. Convert epoch-second timestamps to timezone-aware UTC timestamps.
8. Reject malformed, duplicate, out-of-order, empty, or OHLC-inconsistent responses.
9. Reject negative volume and missing or invalid volume.
10. Validate combined chunk responses for strict chronological ordering and no duplicates; hash concatenated raw chunk bodies in request order.
11. Label data as unadjusted/unknown unless Dhan explicitly confirms an adjustment basis.
12. Do not implement automatic retries, background retrieval, order APIs, account APIs, positions, holdings, funds, or WebSocket behavior.

## Public instrument-master snapshot rules

1. Download the fixed detailed CSV only through an explicit user-invoked sync.
2. Normalize Dhan exchange and segment values into canonical identities such as `DHAN:NSE:NSE_EQ:<security_id>`, `DHAN:NSE:NSE_FNO:<security_id>`, `DHAN:NSE:IDX_I:<security_id>`, and `DHAN:MCX:MCX_COMM:<security_id>`.
3. Preserve provider security IDs as text; symbols and display names are metadata, not identity.
4. Reject missing required fields, malformed dates/numbers, invalid option markers, unsupported mappings, and duplicate canonical identities.
5. Persist each accepted response through `PublicInstrumentSourceService` and `SqliteInstrumentSnapshotRepository`; content-identical downloads update only local check time and never replace the retained snapshot.
6. Never refresh the source during import, page render, status display, or historical-data retrieval.
