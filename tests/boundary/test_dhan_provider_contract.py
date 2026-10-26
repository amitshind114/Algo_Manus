"""Contract-gate tests: Dhan historical integration requires a confirmed provider contract."""

from pathlib import Path

import pytest

DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"
CONTRACT_PATH = DOCS_ROOT / "dhan_provider_contract.md"

REQUIRED_FIELDS = (
    "API base URL",
    "API version",
    "Daily candles endpoint",
    "Intraday candles endpoint",
    "HTTP method",
    "Authentication header",
    "Client identifier requirement",
    "Token lifetime",
    "Token refresh behavior",
    "Security ID field",
    "Exchange segment field",
    "Supported exchange segments",
    "Supported daily intervals",
    "Supported intraday intervals",
    "Maximum intraday request window",
    "Daily request bounds",
    "Intraday request bounds",
    "Pagination or chunking behavior",
    "Timestamp timezone",
    "Candle timestamp semantics",
    "OHLCV response fields",
    "Missing volume policy",
    "Error and status-code contract",
    "Rate limits",
    "Data entitlement and permitted use",
    "Corporate-action adjustment basis",
    "Historical coverage and retention",
    "Static IP requirement for historical endpoint",
)


def test_provider_contract_exists():
    assert CONTRACT_PATH.exists()


def test_provider_contract_is_confirmed():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "Status: CONFIRMED - PHASE 1 COMPLETE" in text


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_every_required_contract_field_is_present(field):
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert field in text, f"Missing required Dhan contract field: {field}"


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_every_required_contract_field_is_confirmed(field):
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    row_prefix = f"| {field} |"
    matching = [line for line in text.splitlines() if line.startswith(row_prefix)]
    assert matching, f"Missing contract row: {field}"
    assert "CONFIRMED" in matching[0], f"Contract field is not confirmed: {field}"
    assert "UNCONFIRMED" not in matching[0], f"Contract field remains unconfirmed: {field}"


def test_intraday_window_limit_is_documented():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "90 days per request" in text


def test_epoch_timestamp_semantics_are_documented():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "Unix epoch seconds" in text


def test_data_rate_limit_is_documented():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "5 requests per second" in text
