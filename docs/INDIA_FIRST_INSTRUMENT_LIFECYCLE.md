# India-First Retained Instrument Lifecycle

## Purpose

Option I provides a canonical, **local read-only** lifecycle projection for retained normalized instrument-master snapshots. It presents India-market contract metadata and review requirements without treating a display name as an identity or adding any broker, price, account, paper-broker, or execution capability.

> Instrument identity remains `broker:exchange:segment:broker_token`. A tradingsymbol, display name, expiry, strike, lot size or tick size is display and contract metadata, never a safe automatic remapping key.

## Canonical retained contract fields

| Field | Meaning in the local projection | Supported examples |
| --- | --- | --- |
| Exchange and segment | Retained source classification; no exchange connection is created. | `NSE`, `BSE`, `NFO`, `MCX`, `NCDEX`; source-specific segment values. |
| Tradingsymbol and display name | Human-readable source metadata. | Equity symbols, index names and derivative contract symbols. |
| Instrument type | Normalized local type from the retained master. | Equity, index, future, option, commodity and currency. |
| Expiry | Retained dated-contract metadata where supplied. | Futures and options. |
| Strike and option type | Retained option-contract metadata where supplied. | Strike plus `CE` or `PE`. |
| Lot size and tick size | Retained source contract metadata. | Present where the master provides it; derivatives require both in the canonical model. |
| Broker status | Retained source status. | `ACTIVE`, `INACTIVE`, `EXPIRED`, `UNRESOLVED`. |

The project currently normalizes these fields from retained public-master data and local fixture records. It does not assert exchange completeness, current contract specifications, corporate-action accuracy, or legal/compliance suitability. A retained snapshot is evidence of what was downloaded at its timestamp, not proof that the record is current.

## Local lifecycle interpretation

| Lifecycle state | Local interpretation | Review outcome |
| --- | --- | --- |
| `READY` | The current retained record is active and no compared contract metadata difference was found. | No additional local review flag. |
| `REVIEW_REQUIRED` | An active current record differs from its explicitly supplied retained baseline in contract metadata. | Review is required before new research or paper use. |
| `INACTIVE` | The current retained record reports inactive source status. | Review is required. |
| `EXPIRED` | The current retained record reports expired source status. | Review is required. |
| `UNRESOLVED` | The current retained record is unresolved. | Review is required. |
| `MISSING` | A baseline canonical identity is absent from the current retained snapshot. | Explicit mapping review is required; no automatic remapping is performed. |

Compared active records require review when their retained **tradingsymbol, display name, instrument type, expiry, strike, option type, lot size, or tick size** changes. A different canonical identity remains missing because its exchange, segment or broker token changed; the application never infers a replacement from a similar name or contract.

## Workbench boundary

The **Data & instruments** page shows a bounded read-only lifecycle view for the currently retained Angel public master. It displays retained-record/ready/review/derivative/segment counts and up to the existing preview limit of contract rows. The page neither creates a baseline comparison nor changes an instrument; comparisons are application-service inputs for a separately approved local review workflow.

The existing manual public-master download remains the only public-source action. The lifecycle projection itself cannot download, synchronize, map, activate, deactivate, fetch prices, start a session, access accounts, submit paper orders or enable live execution.

This is research and analysis only, not personalized financial advice.
