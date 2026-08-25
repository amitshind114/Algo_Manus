"""Manual, local-only Angel One session acquisition.

Only the documented login and JWT refresh endpoints appear in this adapter.
It never calls profile, funds, holdings, positions, prices, WebSocket, order,
logout or scheduler endpoints.  It accepts local environment values only and
does not persist, log or render credential or token material.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import json
import os
from typing import Any
from urllib.request import Request, urlopen

ANGEL_LOGIN_URI = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
ANGEL_GENERATE_TOKEN_URI = "https://apiconnect.angelone.in/rest/auth/angelbroking/jwt/v1/generateTokens"
_Transport = Callable[[str, bytes, dict[str, str]], bytes]


class AngelSessionConfigurationError(ValueError):
    """Raised before transport when local session configuration is incomplete."""


class AngelSessionResponseError(ValueError):
    """Raised for failed or malformed provider envelopes without response details."""


@dataclass(frozen=True, slots=True)
class AngelSessionCredentials:
    """Local-only values deliberately hidden from representations and exceptions."""

    app_key: str = field(repr=False)
    client_code: str = field(repr=False)
    pin: str = field(repr=False)
    totp: str = field(repr=False)
    mac_address: str = field(repr=False)
    local_ip: str = field(repr=False)
    public_ip: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.app_key,
                self.client_code,
                self.pin,
                self.totp,
                self.mac_address,
                self.local_ip,
                self.public_ip,
            )
        ):
            raise AngelSessionConfigurationError(
                "all ALGO_MANUS_ANGEL session environment values are required"
            )


@dataclass(frozen=True, slots=True)
class AngelSessionTokens:
    """In-memory-only token bundle; values are never visible through ``repr``."""

    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    feed_token: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.access_token, self.refresh_token, self.feed_token)):
            raise AngelSessionResponseError("Angel session response is missing a required token")


def _post_json(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
    """Perform one explicit request to an approved fixed session endpoint."""

    request = Request(uri, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=30) as response:  # noqa: S310 - approved fixed Angel session endpoint
        return response.read()


class AngelSessionGateway:
    """Acquire or refresh a transient Angel session without persistence.

    The gateway owns no database, filesystem state, background thread or timer.
    ``transport`` is injectable only for deterministic tests.  The dynamic TOTP
    code is read verbatim from local environment at construction; it is never
    generated from a shared seed and is never accepted through the user interface.
    """

    def __init__(
        self,
        *,
        credentials: AngelSessionCredentials | None,
        transport: _Transport | None = None,
        configuration_error: str | None = None,
    ) -> None:
        self._credentials = credentials
        self._transport = transport or _post_json
        self._configuration_error = configuration_error

    @classmethod
    def from_environment(cls) -> "AngelSessionGateway":
        values = {
            "app_key": os.environ.get("ALGO_MANUS_ANGEL_APP_KEY", "").strip(),
            "client_code": os.environ.get("ALGO_MANUS_ANGEL_CLIENT_CODE", "").strip(),
            "pin": os.environ.get("ALGO_MANUS_ANGEL_PIN", "").strip(),
            "totp": os.environ.get("ALGO_MANUS_ANGEL_TOTP", "").strip(),
            "mac_address": os.environ.get("ALGO_MANUS_ANGEL_MAC_ADDRESS", "").strip(),
            "local_ip": os.environ.get("ALGO_MANUS_ANGEL_LOCAL_IP", "").strip(),
            "public_ip": os.environ.get("ALGO_MANUS_ANGEL_PUBLIC_IP", "").strip(),
        }
        if not any(values.values()):
            return cls(credentials=None)
        if not all(values.values()):
            return cls(
                credentials=None,
                configuration_error=(
                    "ALGO_MANUS_ANGEL_APP_KEY, CLIENT_CODE, PIN, TOTP, MAC_ADDRESS, "
                    "LOCAL_IP and PUBLIC_IP must be configured together"
                ),
            )
        return cls(credentials=AngelSessionCredentials(**values))

    @property
    def credentials_configured(self) -> bool:
        return self._credentials is not None and self._configuration_error is None

    @property
    def configuration_message(self) -> str:
        return self._configuration_error or (
            "ALGO_MANUS_ANGEL_APP_KEY, ALGO_MANUS_ANGEL_CLIENT_CODE, ALGO_MANUS_ANGEL_PIN, "
            "ALGO_MANUS_ANGEL_TOTP, ALGO_MANUS_ANGEL_MAC_ADDRESS, ALGO_MANUS_ANGEL_LOCAL_IP "
            "and ALGO_MANUS_ANGEL_PUBLIC_IP are required for local session configuration"
            if self._credentials is None
            else "configured"
        )

    def authenticate(self) -> AngelSessionTokens:
        """Perform one caller-initiated credential/TOTP login; never persist its output."""

        credentials = self._configured_credentials()
        return self._request_tokens(
            ANGEL_LOGIN_URI,
            {
                "clientcode": credentials.client_code,
                "password": credentials.pin,
                "totp": credentials.totp,
            },
            self._headers(credentials),
        )

    def refresh(self, tokens: AngelSessionTokens) -> AngelSessionTokens:
        """Perform one caller-initiated refresh for an existing in-memory session."""

        credentials = self._configured_credentials()
        headers = self._headers(credentials)
        headers["Authorization"] = f"Bearer {tokens.access_token}"
        return self._request_tokens(
            ANGEL_GENERATE_TOKEN_URI,
            {"refreshToken": tokens.refresh_token},
            headers,
        )

    def _configured_credentials(self) -> AngelSessionCredentials:
        if self._credentials is None or self._configuration_error is not None:
            raise AngelSessionConfigurationError(self.configuration_message)
        return self._credentials

    @staticmethod
    def _headers(credentials: AngelSessionCredentials) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": credentials.local_ip,
            "X-ClientPublicIP": credentials.public_ip,
            "X-MACAddress": credentials.mac_address,
            "X-PrivateKey": credentials.app_key,
        }

    def _request_tokens(
        self,
        uri: str,
        payload: dict[str, str],
        headers: dict[str, str],
    ) -> AngelSessionTokens:
        raw_content = self._transport(
            uri,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers,
        )
        try:
            envelope: Any = json.loads(raw_content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AngelSessionResponseError("Angel session response must be UTF-8 JSON") from exc
        if not isinstance(envelope, dict):
            raise AngelSessionResponseError("Angel session response must be an object")
        if envelope.get("status") is not True:
            code = str(envelope.get("errorcode") or "unknown_error")
            raise AngelSessionResponseError(f"Angel session request failed: {code}")
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise AngelSessionResponseError("Angel session response is missing token data")
        try:
            return AngelSessionTokens(
                access_token=str(data["jwtToken"]),
                refresh_token=str(data["refreshToken"]),
                feed_token=str(data["feedToken"]),
            )
        except KeyError as exc:
            raise AngelSessionResponseError("Angel session response is missing a required token") from exc
