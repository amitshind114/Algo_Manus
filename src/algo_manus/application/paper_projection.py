"""Deterministic replay of local immutable paper events into paper-only state.

Cash, positions and realised P&L move only when replay applies retained local
fill evidence.  Intent, risk, acceptance, cancellation and reconciliation do
not themselves change portfolio values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Protocol

from algo_manus.domain.execution import ReconciliationDisposition
from algo_manus.domain.paper import (
    PaperEvent,
    PaperEventType,
    PaperOrderLifecycle,
    PaperOrderProjection,
    PaperOrderStatus,
    PaperPortfolioProjection,
    PaperPositionProjection,
)
from algo_manus.domain.risk import OrderSide


class PaperEventReadPort(Protocol):
    def events(self, limit: int = 1_000) -> tuple[PaperEvent, ...]: ...


@dataclass
class _MutablePosition:
    quantity: int = 0
    average_entry_price: float = 0.0


@dataclass
class _MutableOrder:
    instrument_id: str
    side: OrderSide | None = None
    quantity: int | None = None
    status: PaperOrderStatus = PaperOrderStatus.PENDING_RISK
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    fill_price: float | None = None
    filled_quantity: int = 0
    risk_seen: bool = False
    reconciliation_disposition: ReconciliationDisposition | None = None


class PaperPortfolioProjector:
    """Replays self-describing local paper events; it never creates or changes them."""

    def replay(self, events: tuple[PaperEvent, ...], *, starting_cash: float) -> PaperPortfolioProjection:
        if starting_cash < 0:
            raise ValueError("starting_cash cannot be negative")
        cash = starting_cash
        realized_pnl = 0.0
        positions: dict[str, _MutablePosition] = {}
        orders: dict[str, _MutableOrder] = {}
        unprojectable: list[str] = []

        for event in events:
            payload = self._payload(event, unprojectable)
            if payload is None:
                continue
            order = orders.setdefault(event.order_id, _MutableOrder(instrument_id=event.instrument_id))
            if order.instrument_id != event.instrument_id:
                self._invalid(event.event_id, unprojectable)
                continue
            risk_allowed: bool | None = None
            if event.event_type is PaperEventType.RISK_DECISION:
                candidate = payload.get("allowed")
                if not isinstance(candidate, bool):
                    self._invalid(event.event_id, unprojectable)
                    continue
                risk_allowed = candidate
                order.risk_seen = True
            if event.event_type is PaperEventType.ORDER_REJECTED and not order.risk_seen:
                self._invalid(event.event_id, unprojectable)
                continue
            next_status = PaperOrderLifecycle.apply(order.status, event.event_type, risk_allowed=risk_allowed)
            if next_status is None:
                self._invalid(event.event_id, unprojectable)
                continue

            if event.event_type is PaperEventType.ORDER_PROPOSED:
                if not self._apply_order_terms(order, payload):
                    self._invalid(event.event_id, unprojectable)
                    continue
                order.status = next_status
                continue
            if event.event_type is PaperEventType.RISK_DECISION:
                order.status = next_status
                continue
            if event.event_type in {PaperEventType.ORDER_ACCEPTED, PaperEventType.ORDER_SUBMITTED}:
                if not self._apply_order_terms(order, payload):
                    self._invalid(event.event_id, unprojectable)
                    continue
                order.status = next_status
                order.submitted_at = event.occurred_at
                continue
            if event.event_type is PaperEventType.ORDER_WORKING:
                if not self._matching_optional_terms(order, payload):
                    self._invalid(event.event_id, unprojectable)
                    continue
                order.status = next_status
                continue
            if event.event_type in {PaperEventType.ORDER_REJECTED, PaperEventType.ORDER_CANCELLED}:
                if not self._matching_optional_terms(order, payload):
                    self._invalid(event.event_id, unprojectable)
                    continue
                order.status = next_status
                continue
            if event.event_type in {PaperEventType.ORDER_PARTIALLY_FILLED, PaperEventType.ORDER_FILLED}:
                applied = self._apply_fill(order, event, payload, positions, unprojectable)
                if applied is None:
                    continue
                cash_delta, pnl_delta = applied
                cash += cash_delta
                realized_pnl += pnl_delta
                order.status = next_status
                order.filled_at = event.occurred_at
                order.fill_price = float(payload["fill_price"])
                continue
            if event.event_type is PaperEventType.RECONCILIATION_RECORDED:
                try:
                    disposition = ReconciliationDisposition(payload.get("disposition"))
                except ValueError:
                    self._invalid(event.event_id, unprojectable)
                    continue
                if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
                    self._invalid(event.event_id, unprojectable)
                    continue
                order.status = next_status
                order.reconciliation_disposition = disposition
                continue
            self._invalid(event.event_id, unprojectable)

        projected_positions = tuple(
            PaperPositionProjection(instrument_id=instrument_id, quantity=position.quantity, average_entry_price=position.average_entry_price)
            for instrument_id, position in sorted(positions.items())
            if position.quantity != 0
        )
        projected_orders = tuple(
            PaperOrderProjection(
                order_id=order_id,
                instrument_id=order.instrument_id,
                side=order.side,
                quantity=order.quantity,
                status=order.status,
                submitted_at=order.submitted_at,
                filled_at=order.filled_at,
                fill_price=order.fill_price,
                filled_quantity=order.filled_quantity,
                remaining_quantity=order.quantity - order.filled_quantity if order.quantity is not None else None,
                reconciliation_disposition=order.reconciliation_disposition,
            )
            for order_id, order in sorted(orders.items())
        )
        accepted_statuses = {
            PaperOrderStatus.ACCEPTED,
            PaperOrderStatus.WORKING,
            PaperOrderStatus.PARTIALLY_FILLED,
            PaperOrderStatus.FILLED,
            PaperOrderStatus.CANCELLED,
            PaperOrderStatus.RECONCILED,
        }
        return PaperPortfolioProjection(
            starting_cash=starting_cash,
            cash=cash,
            realized_pnl=realized_pnl,
            positions=projected_positions,
            orders=projected_orders,
            session_order_count=sum(order.status in accepted_statuses for order in orders.values()),
            unprojectable_event_ids=tuple(unprojectable),
        )

    def _apply_fill(
        self,
        order: _MutableOrder,
        event: PaperEvent,
        payload: dict[str, object],
        positions: dict[str, _MutablePosition],
        unprojectable: list[str],
    ) -> tuple[float, float] | None:
        side = self._side(payload)
        quantity = self._quantity(payload)
        fill_price = payload.get("fill_price")
        cumulative = payload.get("cumulative_filled_quantity")
        if cumulative is None and event.event_type is PaperEventType.ORDER_FILLED:
            cumulative = order.quantity
        if (
            order.side is None
            or order.quantity is None
            or side is not order.side
            or quantity is None
            or not isinstance(cumulative, int)
            or cumulative != order.filled_quantity + quantity
            or cumulative > order.quantity
            or not isinstance(fill_price, (int, float))
            or fill_price <= 0
        ):
            self._invalid(event.event_id, unprojectable)
            return None
        if event.event_type is PaperEventType.ORDER_PARTIALLY_FILLED and not 0 < cumulative < order.quantity:
            self._invalid(event.event_id, unprojectable)
            return None
        if event.event_type is PaperEventType.ORDER_FILLED and cumulative != order.quantity:
            self._invalid(event.event_id, unprojectable)
            return None
        position = positions.setdefault(event.instrument_id, _MutablePosition())
        order.filled_quantity = cumulative
        if side is OrderSide.BUY:
            new_quantity = position.quantity + quantity
            position.average_entry_price = ((position.quantity * position.average_entry_price) + (quantity * float(fill_price))) / new_quantity
            position.quantity = new_quantity
            return (-quantity * float(fill_price), 0.0)
        if quantity > position.quantity:
            self._invalid(event.event_id, unprojectable)
            order.filled_quantity -= quantity
            return None
        realized = quantity * (float(fill_price) - position.average_entry_price)
        position.quantity -= quantity
        if position.quantity == 0:
            position.average_entry_price = 0.0
        return (quantity * float(fill_price), realized)

    @staticmethod
    def _apply_order_terms(order: _MutableOrder, payload: dict[str, object]) -> bool:
        side = PaperPortfolioProjector._side(payload)
        quantity = PaperPortfolioProjector._quantity(payload)
        if side is None or quantity is None:
            return False
        if order.side is not None and order.side is not side:
            return False
        if order.quantity is not None and order.quantity != quantity:
            return False
        order.side = side
        order.quantity = quantity
        return True

    @staticmethod
    def _matching_optional_terms(order: _MutableOrder, payload: dict[str, object]) -> bool:
        side = PaperPortfolioProjector._side(payload)
        quantity = PaperPortfolioProjector._quantity(payload)
        if side is not None and order.side is not None and side is not order.side:
            return False
        if quantity is not None and order.quantity is not None and quantity != order.quantity:
            return False
        return True

    @staticmethod
    def _payload(event: PaperEvent, unprojectable: list[str]) -> dict[str, object] | None:
        try:
            canonical = json.loads(event.payload)
            payload = canonical.get("payload")
        except (TypeError, json.JSONDecodeError):
            PaperPortfolioProjector._invalid(event.event_id, unprojectable)
            return None
        if not isinstance(payload, dict):
            PaperPortfolioProjector._invalid(event.event_id, unprojectable)
            return None
        return payload

    @staticmethod
    def _side(payload: dict[str, object]) -> OrderSide | None:
        value = payload.get("side")
        try:
            return OrderSide(value) if isinstance(value, str) else None
        except ValueError:
            return None

    @staticmethod
    def _quantity(payload: dict[str, object]) -> int | None:
        value = payload.get("quantity")
        return value if isinstance(value, int) and value > 0 else None

    @staticmethod
    def _invalid(event_id: str, unprojectable: list[str]) -> None:
        if event_id not in unprojectable:
            unprojectable.append(event_id)


class PaperOperationsReadService:
    """Typed local read path for an append-only paper ledger and its replay."""

    def __init__(self, ledger: PaperEventReadPort, projector: PaperPortfolioProjector | None = None) -> None:
        self._ledger = ledger
        self._projector = projector or PaperPortfolioProjector()

    def events(self, limit: int = 1_000) -> tuple[PaperEvent, ...]:
        return self._ledger.events(limit)

    def portfolio(self, *, starting_cash: float, limit: int = 1_000) -> PaperPortfolioProjection:
        return self._projector.replay(self.events(limit), starting_cash=starting_cash)
