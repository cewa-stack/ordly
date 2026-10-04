"""
Endpointy HTTP /api/v1/customer-cases - rejestr anulowań i zwrotów
pieniędzy (app/domain/customer_cases.py).

Dostęp tylko z tokenem ORDLY API (router w app/api/router.py). Rekordy
nie zawierają telefonu, e-maila ani imienia i nazwiska kupującego.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    CaseReasonChangeOut,
    CustomerCaseOut,
    CustomerCaseUpdateIn,
    case_reason_change_out,
    customer_case_out,
)
from app.container import Container
from app.domain.customer_cases import CaseFilters

router = APIRouter()

_Kind = Literal["CANCELLATION", "REFUND", "BOTH"]
_Reason = Literal["OUT_OF_STOCK", "PAYMENT_PROBLEM", "BUYER_RESIGNED", "OTHER", "MISSING"]
_Handling = Literal["REPORTED", "IN_PROGRESS", "DONE"]
_Source = Literal["ALLEGRO_ORDER", "ALLEGRO_RETURN", "APP_STATUS", "MIGRATION"]


@router.get("/customer-cases", response_model=list[CustomerCaseOut])
async def list_customer_cases(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    kind: Annotated[list[_Kind] | None, Query()] = None,
    handling_status: _Handling | None = None,
    reason: _Reason | None = None,
    source: _Source | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CustomerCaseOut]:
    """
    Rekordy anulowań i zwrotów pieniędzy, od najnowszego zdarzenia.

    Filtry (łączone przez AND): rodzaj (`kind`, można podać kilka), status
    obsługi, powód (`MISSING` = nieuzupełniony), źródło zdarzenia i zakres
    dat zdarzenia (`date_from` włącznie, `date_to` wyłącznie; UTC).
    """
    filters = CaseFilters(
        kinds=tuple(kind or ()),
        handling_status=handling_status,
        reason=None if reason == "MISSING" else reason,
        reason_missing=reason == "MISSING",
        source=source,
        date_from=_naive_utc(date_from),
        date_to=_naive_utc(date_to),
    )
    service = container.customer_case_service(session)
    return [customer_case_out(c) for c in await service.find(filters, limit, offset)]


@router.patch("/customer-cases/{case_id}", response_model=CustomerCaseOut)
async def update_customer_case(
    container: Annotated[Container, Depends(get_container)],
    case_id: int,
    payload: CustomerCaseUpdateIn,
) -> CustomerCaseOut:
    """
    Ręczna zmiana powodu i/lub statusu obsługi. Pole pominięte = bez zmian,
    `"reason": null` = powód "nieuzupełnione". Zmiana powodu trafia do
    historii.
    """
    fields = payload.model_fields_set
    async with container.session_scope() as session:
        case = await container.customer_case_service(session).update(
            case_id,
            reason=payload.reason if "reason" in fields else None,
            clear_reason="reason" in fields and payload.reason is None,
            handling_status=payload.handling_status,
        )
    return customer_case_out(case)


@router.get("/customer-cases/{case_id}/reason-history", response_model=list[CaseReasonChangeOut])
async def customer_case_reason_history(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    case_id: int,
) -> list[CaseReasonChangeOut]:
    """Historia powodu - od najnowszej zmiany."""
    service = container.customer_case_service(session)
    return [case_reason_change_out(c) for c in await service.reason_history(case_id)]


def _naive_utc(value: datetime | None) -> datetime | None:
    """Baza trzyma naiwny UTC - data ze strefą jest przeliczana i obcinana."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
