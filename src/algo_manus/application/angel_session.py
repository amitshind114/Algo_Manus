"""Display-safe, in-memory session lifecycle for the read-only Angel adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from algo_manus.infrastructure.sessions.angel_one import AngelSessionGateway, AngelSessionTokens


class AccessTokenConsumer(Protocol):
    """Narrow handoff boundary for the already-approved read-only adapter."""

    def set_access_token(self, access_token: str) -> None: ...

    def clear_access_token(self) -> None: ...


@dataclass(frozen=True, slots=True)
class LocalAngelSessionStatus:
    """Session state intentionally excludes all credential and token values."""

    session_state: str
    credentials_configured: bool
    acquired_at: datetime | None
    manual_action_required: bool


class LocalAngelSessionService:
    """Coordinate manual login/refresh and in-memory token handoff only.

    ``forget`` is local memory cleanup, not a remote logout call.  No session
    value is written to SQLite, a file, a log, a user interface or an exception.
    """

    def __init__(self, gateway: AngelSessionGateway, consumer: AccessTokenConsumer) -> None:
        self._gateway = gateway
        self._consumer = consumer
        self._tokens: AngelSessionTokens | None = None
        self._acquired_at: datetime | None = None

    def status(self) -> LocalAngelSessionStatus:
        if self._tokens is None:
            return LocalAngelSessionStatus(
                session_state="not_started" if self._gateway.credentials_configured else "local_configuration_required",
                credentials_configured=self._gateway.credentials_configured,
                acquired_at=None,
                manual_action_required=True,
            )
        return LocalAngelSessionStatus(
            session_state="active_in_memory",
            credentials_configured=True,
            acquired_at=self._acquired_at,
            manual_action_required=False,
        )

    def start(self, *, now: datetime | None = None) -> LocalAngelSessionStatus:
        """Manually acquire one session and hand only its JWT to the consumer."""

        self._tokens = self._gateway.authenticate()
        self._consumer.set_access_token(self._tokens.access_token)
        self._acquired_at = self._now(now)
        return self.status()

    def refresh(self, *, now: datetime | None = None) -> LocalAngelSessionStatus:
        """Manually refresh an active in-memory session and replace its JWT handoff."""

        if self._tokens is None:
            raise ValueError("an active local session is required before refresh")
        self._tokens = self._gateway.refresh(self._tokens)
        self._consumer.set_access_token(self._tokens.access_token)
        self._acquired_at = self._now(now)
        return self.status()

    def forget(self) -> LocalAngelSessionStatus:
        """Discard local token references and clear the read-only adapter handoff."""

        self._tokens = None
        self._acquired_at = None
        self._consumer.clear_access_token()
        return self.status()

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("session lifecycle timestamps must be timezone-aware")
        return current
