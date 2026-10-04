"""Implementacja CustomerCaseRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.customer_case_model import (
    CustomerCaseModel,
    CustomerCaseReasonChangeModel,
)
from app.domain.customer_cases import CaseFilters, CaseReasonChange, CustomerCase
from app.domain.interfaces.customer_case_repository import CustomerCaseRepository

#: Data zdarzenia do sortowania i filtra dat: anulowanie, potem zwrot
#: pieniędzy, a gdy obu brak (dane sprzed wdrożenia) - data zamówienia
#: i na końcu data utworzenia rekordu.
_EVENT_DATE = func.coalesce(
    CustomerCaseModel.cancelled_at,
    CustomerCaseModel.refunded_at,
    CustomerCaseModel.order_date,
    CustomerCaseModel.created_at,
)

_FIELDS = (
    "marketplace",
    "order_external_id",
    "allegro_order_id",
    "kind",
    "source",
    "handling_status",
    "buyer_login",
    "order_date",
    "cancelled_at",
    "refunded_at",
    "reason",
    "reason_detail",
)


class SqliteCustomerCaseRepository(CustomerCaseRepository):
    """Rejestr anulowań i zwrotów pieniędzy w SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_order(self, marketplace: str, order_external_id: str) -> CustomerCase | None:
        stmt = select(CustomerCaseModel).where(
            CustomerCaseModel.marketplace == marketplace,
            CustomerCaseModel.order_external_id == order_external_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get(self, case_id: int) -> CustomerCase | None:
        model = await self._session.get(CustomerCaseModel, case_id)
        return self._to_domain(model) if model else None

    async def add(self, case: CustomerCase) -> CustomerCase:
        model = CustomerCaseModel(**{name: getattr(case, name) for name in _FIELDS})
        self._session.add(model)
        await self._session.flush()
        return self._to_domain(model)

    async def update(self, case: CustomerCase) -> CustomerCase:
        assert case.id is not None
        model = await self._session.get(CustomerCaseModel, case.id)
        assert model is not None
        for name in _FIELDS:
            setattr(model, name, getattr(case, name))
        await self._session.flush()
        return self._to_domain(model)

    async def find(self, filters: CaseFilters, limit: int, offset: int = 0) -> list[CustomerCase]:
        conditions: list[Any] = []
        if filters.kinds:
            conditions.append(CustomerCaseModel.kind.in_(list(filters.kinds)))
        if filters.handling_status:
            conditions.append(CustomerCaseModel.handling_status == filters.handling_status)
        if filters.reason_missing:
            conditions.append(CustomerCaseModel.reason.is_(None))
        elif filters.reason:
            conditions.append(CustomerCaseModel.reason == filters.reason)
        if filters.source:
            conditions.append(CustomerCaseModel.source == filters.source)
        if filters.date_from:
            conditions.append(filters.date_from <= _EVENT_DATE)
        if filters.date_to:
            conditions.append(filters.date_to > _EVENT_DATE)
        stmt = (
            select(CustomerCaseModel)
            .where(*conditions)
            .order_by(_EVENT_DATE.desc(), CustomerCaseModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_domain(m) for m in (await self._session.execute(stmt)).scalars()]

    async def record_reason_change(self, change: CaseReasonChange) -> None:
        self._session.add(
            CustomerCaseReasonChangeModel(
                case_id=change.case_id,
                previous_reason=change.previous_reason,
                new_reason=change.new_reason,
                source=change.source,
                changed_at=change.changed_at,
            )
        )
        await self._session.flush()

    async def reason_history(self, case_id: int) -> list[CaseReasonChange]:
        stmt = (
            select(CustomerCaseReasonChangeModel)
            .where(CustomerCaseReasonChangeModel.case_id == case_id)
            .order_by(
                CustomerCaseReasonChangeModel.changed_at.desc(),
                CustomerCaseReasonChangeModel.id.desc(),
            )
        )
        return [
            CaseReasonChange(
                case_id=m.case_id,
                previous_reason=m.previous_reason,
                new_reason=m.new_reason,
                source=m.source,
                changed_at=m.changed_at,
            )
            for m in (await self._session.execute(stmt)).scalars()
        ]

    @staticmethod
    def _to_domain(model: CustomerCaseModel) -> CustomerCase:
        return CustomerCase(
            id=model.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            **{name: getattr(model, name) for name in _FIELDS},
        )
