"""Read-only Dhan historical-data transport.

This module posts only to Dhan's documented historical-candle endpoints.
It deliberately does not access account data, positions, holdings, funds,
order endpoints, live market feeds, WebSockets, or any execution capability.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.request import Request, urlopen

DHAN_API_BASE_URI = "https://api.dhan.co/v2"
DHAN_DAILY_CANDLE_URI = f"{DHAN_API_BASE_URI}/charts/historical"
DHAN_INTRADAY_CANDLE_URI = f"{DHAN_API_BASE_URI}/charts/intraday"

_Transport = Callable[[str, bytes, dict[str, str]], bytes]


def post_json(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
    """Perform one explicit request to a fixed Dhan historical-data endpoint."""

    request = Request(uri, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=30) as response:  # noqa: S310 - approved fixed broker endpoint
        return response.read()
