"""Contract-gate tests: Dhan integration is blocked until its provider contract is confirmed."""

from pathlib import Path

import pytest

DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"
CONTRACT_PATH = DOCS_ROOT / "dhan_provider_contract.md"

REQUIRED_FIELDS = (
    "API base URL",
    "API version",
    "Historical candles endpoint",
    "HTTP method",
    "Authentication header",
    "Client identifier requirement",
    "Token lifetime",
    "Token refresh behavior",
    "Security ID field",
    "Exchange segment field",
    "Supported intervals",
    "Maximum request window per interval",
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


def test_provider_contract_is_explicitly_blocked_until_confirmed():
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert "Status: DRAFT - IMPLEMENTATION BLOCKED" in text


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_every_required_contract_field_is_present(field):
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    assert field in text, f"Missing required Dhan contract field: {field}"


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_no_required_contract_field_is_confirmed_yet(field):
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    row_prefix = f"| {field} |"
    matching = [line for line in text.splitlines() if line.startswith(row_prefix)]
    assert matching, f"Missing contract row: {field}"
    assert "UNCONFIRMED" in matching[0], f"Contract field must remain unconfirmed: {field}"
