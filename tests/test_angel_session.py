from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from algo_manus.application.angel_session import LocalAngelSessionService
from algo_manus.infrastructure.sessions.angel_one import (
    ANGEL_GENERATE_TOKEN_URI,
    ANGEL_LOGIN_URI,
    AngelSessionConfigurationError,
    AngelSessionGateway,
    AngelSessionResponseError,
    AngelSessionCredentials,
)


class AccessTokenConsumer:
    def __init__(self) -> None:
        self.values: list[str | None] = []

    def set_access_token(self, access_token: str) -> None:
        self.values.append(access_token)

    def clear_access_token(self) -> None:
        self.values.append(None)


class AngelSessionGatewayTests(unittest.TestCase):
    def _credentials(self) -> AngelSessionCredentials:
        return AngelSessionCredentials(
            app_key="test-app-key",
            client_code="test-client-code",
            pin="test-pin",
            totp="123456",
            mac_address="00:11:22:33:44:55",
            local_ip="192.0.2.10",
            public_ip="198.51.100.10",
        )

    def test_login_normalizes_the_documented_token_bundle_without_exposing_it_in_repr(self) -> None:
        captured: dict[str, object] = {}

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            captured.update(uri=uri, body=json.loads(body), headers=headers)
            return json.dumps(
                {
                    "status": True,
                    "message": "SUCCESS",
                    "errorcode": "",
                    "data": {
                        "jwtToken": "test-jwt-token",
                        "refreshToken": "test-refresh-token",
                        "feedToken": "test-feed-token",
                    },
                }
            ).encode()

        session = AngelSessionGateway(credentials=self._credentials(), transport=transport).authenticate()

        self.assertEqual(captured["uri"], ANGEL_LOGIN_URI)
        self.assertEqual(
            captured["body"],
            {"clientcode": "test-client-code", "password": "test-pin", "totp": "123456"},
        )
        self.assertNotIn("Authorization", captured["headers"])
        self.assertEqual(captured["headers"]["X-MACAddress"], "00:11:22:33:44:55")
        self.assertEqual(captured["headers"]["X-ClientLocalIP"], "192.0.2.10")
        self.assertEqual(captured["headers"]["X-ClientPublicIP"], "198.51.100.10")
        self.assertNotIn("test-jwt-token", repr(session))
        self.assertNotIn("test-refresh-token", repr(session))

    def test_missing_local_configuration_fails_before_transport(self) -> None:
        calls = 0

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            nonlocal calls
            calls += 1
            return b"{}"

        gateway = AngelSessionGateway(credentials=None, transport=transport)
        with self.assertRaisesRegex(AngelSessionConfigurationError, "ALGO_MANUS_ANGEL"):
            gateway.authenticate()
        self.assertEqual(calls, 0)

    def test_failed_response_uses_only_provider_error_code(self) -> None:
        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            return json.dumps(
                {
                    "status": False,
                    "message": "test-client-code must never be reflected",
                    "errorcode": "AB1050",
                    "data": None,
                }
            ).encode()

        with self.assertRaisesRegex(AngelSessionResponseError, "AB1050") as raised:
            AngelSessionGateway(credentials=self._credentials(), transport=transport).authenticate()
        self.assertNotIn("test-client-code", str(raised.exception))


class LocalAngelSessionServiceTests(unittest.TestCase):
    def test_manual_lifecycle_hands_tokens_to_consumer_then_forgets_them_without_network_logout(self) -> None:
        calls: list[str] = []

        def transport(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
            calls.append(uri)
            if uri == ANGEL_LOGIN_URI:
                payload = {"jwtToken": "first-jwt", "refreshToken": "first-refresh", "feedToken": "first-feed"}
            else:
                payload = {"jwtToken": "second-jwt", "refreshToken": "second-refresh", "feedToken": "second-feed"}
            return json.dumps({"status": True, "message": "SUCCESS", "errorcode": "", "data": payload}).encode()

        consumer = AccessTokenConsumer()
        service = LocalAngelSessionService(
            AngelSessionGateway(
                credentials=AngelSessionGatewayTests()._credentials(),
                transport=transport,
            ),
            consumer,
        )
        now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)

        started = service.start(now=now)
        refreshed = service.refresh(now=now)
        cleared = service.forget()

        self.assertEqual(started.session_state, "active_in_memory")
        self.assertEqual(refreshed.session_state, "active_in_memory")
        self.assertEqual(cleared.session_state, "not_started")
        self.assertEqual(calls, [ANGEL_LOGIN_URI, ANGEL_GENERATE_TOKEN_URI])
        self.assertEqual(consumer.values, ["first-jwt", "second-jwt", None])
        self.assertIsNone(cleared.acquired_at)
        self.assertNotIn("first-jwt", repr(cleared))

    def test_refresh_and_forget_fail_closed_when_no_session_is_active(self) -> None:
        consumer = AccessTokenConsumer()
        service = LocalAngelSessionService(AngelSessionGateway(credentials=None), consumer)

        with self.assertRaisesRegex(ValueError, "active local session"):
            service.refresh(now=datetime(2026, 8, 25, tzinfo=timezone.utc))
        self.assertEqual(service.forget().session_state, "local_configuration_required")
        self.assertEqual(consumer.values, [None])


if __name__ == "__main__":
    unittest.main()
