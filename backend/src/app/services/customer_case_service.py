"""
Rejestr anulowań i zwrotów pieniędzy - zapis zdarzeń i obsługa rekordów.

Zdarzenia przychodzą z Event Busa (subskrybenci w app/event_subscriptions.py):
- anulowanie zamówienia wykryte przez synchronizację z Allegro;
- zwrot klienta, w którym pieniądze zostały oddane;
- ręczne ustawienie statusu "Anulowane" w aplikacji.

Rekord jest jeden na zamówienie - ponowne wykrycie tylko go uzupełnia
(app/domain/customer_cases.py:merge_case). Serwis nie loguje loginu
kupującego - w logach jest tylko numer zamówienia.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from loguru import logger

from app.domain.customer_cases import (
    HANDLING_LABELS,
    KIND_CANCELLATION,
    KIND_REFUND,
    REASON_LABELS,
    REASON_SOURCE_ALLEGRO,
    REASON_SOURCE_MANUAL,
    SOURCE_ALLEGRO_RETURN,
    CaseFilters,
    CaseReasonChange,
    CustomerCase,
    clean_login,
    merge_case,
    reason_from_allegro_return,
)
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.exceptions.domain_exceptions import CustomerCaseNotFoundError
from app.domain.interfaces.customer_case_repository import CustomerCaseRepository
from app.domain.interfaces.order_repository import OrderRepository
from app.utils.time import utc_now

_ALLEGRO_MARKETPLACE = "allegro"


class InvalidCaseValueError(ValueError):
    """Powód albo status obsługi spoza dozwolonej listy."""


class CustomerCaseService:
    """Zapisuje anulowania i zwroty pieniędzy do jednego rejestru."""

    def __init__(
        self, repository: CustomerCaseRepository, order_repository: OrderRepository
    ) -> None:
        self._cases = repository
        self._orders = order_repository

    # ------------------------------------------------------------- zdarzenia

    async def record_cancellation(
        self, order: Order, cancelled_at: datetime, source: str
    ) -> CustomerCase:
        """Anulowanie zamówienia (z Allegro albo ręcznie w aplikacji)."""
        stored = await self._orders.get_by_external_id(order.external_id)
        incoming = CustomerCase(
            marketplace=order.marketplace,
            order_external_id=order.external_id,
            kind=KIND_CANCELLATION,
            source=source,
            allegro_order_id=_allegro_id(order.marketplace, order.external_id),
            buyer_login=clean_login(order.buyer.login),
            # Data złożenia z bazy (pierwsze zobaczenie zamówienia), a nie
            # z bieżącej odpowiedzi marketplace.
            order_date=stored.order_date if stored else order.order_date,
            cancelled_at=cancelled_at,
        )
        return await self._upsert(incoming)

    async def record_refund(self, order_return: OrderReturn, refunded_at: datetime) -> CustomerCase:
        """Zwrot klienta, w którym pieniądze zostały oddane."""
        stored = await self._orders.get_by_external_id(order_return.order_external_id)
        incoming = CustomerCase(
            marketplace=order_return.marketplace,
            order_external_id=order_return.order_external_id,
            kind=KIND_REFUND,
            source=SOURCE_ALLEGRO_RETURN,
            allegro_order_id=_allegro_id(
                order_return.marketplace, order_return.order_external_id
            ),
            buyer_login=clean_login(order_return.buyer_login)
            or (clean_login(stored.buyer.login) if stored else None),
            order_date=stored.order_date if stored else None,
            refunded_at=refunded_at,
            reason=reason_from_allegro_return(order_return.reason_type),
            reason_detail=order_return.reason_type,
        )
        return await self._upsert(incoming)

    async def _upsert(self, incoming: CustomerCase) -> CustomerCase:
        existing = await self._cases.get_by_order(
            incoming.marketplace, incoming.order_external_id
        )
        if existing is None:
            saved = await self._cases.add(incoming)
            assert saved.id is not None
            if saved.reason is not None:
                await self._record_reason(saved.id, None, saved.reason, REASON_SOURCE_ALLEGRO)
            logger.info(
                "Rejestr anulowań i zwrotów: nowy rekord {} ({})",
                saved.order_external_id,
                saved.kind,
            )
            return saved

        merged = merge_case(existing, incoming)
        if merged == existing:
            return existing
        saved = await self._cases.update(merged)
        assert saved.id is not None
        if existing.reason != saved.reason:
            await self._record_reason(
                saved.id, existing.reason, saved.reason, REASON_SOURCE_ALLEGRO
            )
        logger.info(
            "Rejestr anulowań i zwrotów: uzupełniono rekord {} ({})",
            saved.order_external_id,
            saved.kind,
        )
        return saved

    # ------------------------------------------------------- obsługa ręczna

    async def update(
        self,
        case_id: int,
        *,
        reason: str | None = None,
        clear_reason: bool = False,
        handling_status: str | None = None,
    ) -> CustomerCase:
        """
        Ręczna zmiana powodu i/lub statusu obsługi.

        `clear_reason=True` cofa powód do "nieuzupełnione". Każda zmiana
        powodu trafia do historii.
        """
        case = await self._cases.get(case_id)
        if case is None:
            raise CustomerCaseNotFoundError(case_id)
        if reason is not None and reason not in REASON_LABELS:
            raise InvalidCaseValueError(reason)
        if handling_status is not None and handling_status not in HANDLING_LABELS:
            raise InvalidCaseValueError(handling_status)

        new_reason = None if clear_reason else (reason if reason is not None else case.reason)
        updated = replace(
            case,
            reason=new_reason,
            handling_status=handling_status or case.handling_status,
        )
        if updated == case:
            return case
        saved = await self._cases.update(updated)
        if case.reason != saved.reason:
            await self._record_reason(case_id, case.reason, saved.reason, REASON_SOURCE_MANUAL)
        return saved

    async def find(
        self, filters: CaseFilters, limit: int = 200, offset: int = 0
    ) -> list[CustomerCase]:
        return await self._cases.find(filters, limit, offset)

    async def reason_history(self, case_id: int) -> list[CaseReasonChange]:
        if await self._cases.get(case_id) is None:
            raise CustomerCaseNotFoundError(case_id)
        return await self._cases.reason_history(case_id)

    async def _record_reason(
        self, case_id: int, previous: str | None, new: str | None, source: str
    ) -> None:
        await self._cases.record_reason_change(
            CaseReasonChange(
                case_id=case_id,
                previous_reason=previous,
                new_reason=new,
                source=source,
                changed_at=utc_now(),
            )
        )


def _allegro_id(marketplace: str, order_external_id: str) -> str | None:
    """Identyfikator zamówienia w Allegro - tylko dla zamówień z Allegro.pl."""
    return order_external_id if marketplace == _ALLEGRO_MARKETPLACE else None
