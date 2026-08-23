"""Read-only replay of durable local paper events into a deterministic projection."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol

from algo_manus.domain.paper import (
    PaperEvent,
    PaperEventType,
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
    submitted_at: object | None = None
    filled_at: object | None = None
    fill_price: float | None = None


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
            side = self._side(payload)
            quantity = self._quantity(payload)
            if side is not None:
                order.side = side
            if quantity is not None:
                order.quantity = quantity

            if event.event_type is PaperEventType.ORDER_REJECTED:
                order.status = PaperOrderStatus.REJECTED
                continue
            if event.event_type is PaperEventType.ORDER_SUBMITTED:
                if side is None or quantity is None:
                    unprojectable.append(event.event_id)
                    continue
                order.status = PaperOrderStatus.SUBMITTED
                order.submitted_at = event.occurred_at
                continue
            if event.event_type is not PaperEventType.ORDER_FILLED:
                continue

            fill_price = payload.get("fill_price")
            if side is None or quantity is None or not isinstance(fill_price, (int, float)) or fill_price <= 0:
                unprojectable.append(event.event_id)
                continue
            position = positions.setdefault(event.instrument_id, _MutablePosition())
            if side is OrderSide.BUY:
                new_quantity = position.quantity + quantity
                position.average_entry_price = (
                    ((position.quantity * position.average_entry_price) + (quantity * float(fill_price))) / new_quantity
                )
                position.quantity = new_quantity
                cash -= quantity * float(fill_price)
            else:
                if quantity > position.quantity:
                    unprojectable.append(event.event_id)
                    continue
                cash += quantity * float(fill_price)
                realized_pnl += quantity * (float(fill_price) - position.average_entry_price)
                position.quantity -= quantity
                if position.quantity == 0:
                    position.average_entry_price = 0.0
            order.status = PaperOrderStatus.FILLED
            order.filled_at = event.occurred_at
            order.fill_price = float(fill_price)

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
            )
            for order_id, order in sorted(orders.items())
        )
        return PaperPortfolioProjection(
            starting_cash=starting_cash,
            cash=cash,
            realized_pnl=realized_pnl,
            positions=projected_positions,
            orders=projected_orders,
            session_order_count=sum(order.status in {PaperOrderStatus.SUBMITTED, PaperOrderStatus.FILLED} for order in orders.values()),
            unprojectable_event_ids=tuple(unprojectable),
        )

    @staticmethod
    def _payload(event: PaperEvent, unprojectable: list[str]) -> dict[str, object] | None:
        try:
            canonical = json.loads(event.payload)
            payload = canonical.get("payload")
        except (TypeError, json.JSONDecodeError):
            unprojectable.append(event.event_id)
            return None
        if not isinstance(payload, dict):
            unprojectable.append(event.event_id)
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


class PaperOperationsReadService:
    """Typed local read path for an append-only paper ledger and its replay."""

    def __init__(self, ledger: PaperEventReadPort, projector: PaperPortfolioProjector | None = None) -> None:
        self._ledger = ledger
        self._projector = projector or PaperPortfolioProjector()

    def events(self, limit: int = 1_000) -> tuple[PaperEvent, ...]:
        return self._ledger.events(limit)

    def portfolio(self, *, starting_cash: float, limit: int = 1_000) -> PaperPortfolioProjection:
        return self._projector.replay(self.events(limit), starting_cash=starting_cash)
