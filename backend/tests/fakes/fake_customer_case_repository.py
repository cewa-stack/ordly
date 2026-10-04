"""Fake CustomerCaseRepository - rejestr anulowań i zwrotów w pamięci."""

from __future__ import annotations

from dataclasses import replace

from app.domain.customer_cases import CaseFilters, CaseReasonChange, CustomerCase
from app.domain.interfaces.customer_case_repository import CustomerCaseRepository
from app.utils.time import utc_now


class FakeCustomerCaseRepository(CustomerCaseRepository):
    def __init__(self) -> None:
        self.cases: dict[int, CustomerCase] = {}
        self.history: list[CaseReasonChange] = []
        self._next_id = 1

    async def get_by_order(self, marketplace: str, order_external_id: str) -> CustomerCase | None:
        return next(
            (
                c
                for c in self.cases.values()
                if c.marketplace == marketplace and c.order_external_id == order_external_id
            ),
            None,
        )

    async def get(self, case_id: int) -> CustomerCase | None:
        return self.cases.get(case_id)

    async def add(self, case: CustomerCase) -> CustomerCase:
        now = utc_now()
        saved = replace(case, id=self._next_id, created_at=now, updated_at=now)
        self.cases[saved.id] = saved  # type: ignore[index]
        self._next_id += 1
        return saved

    async def update(self, case: CustomerCase) -> CustomerCase:
        assert case.id is not None
        saved = replace(case, updated_at=utc_now())
        self.cases[case.id] = saved
        return saved

    async def find(self, filters: CaseFilters, limit: int, offset: int = 0) -> list[CustomerCase]:
        def ok(c: CustomerCase) -> bool:
            if filters.kinds and c.kind not in filters.kinds:
                return False
            if filters.handling_status and c.handling_status != filters.handling_status:
                return False
            if filters.reason_missing and c.reason is not None:
                return False
            if not filters.reason_missing and filters.reason and c.reason != filters.reason:
                return False
            return not (filters.source and c.source != filters.source)

        found = sorted((c for c in self.cases.values() if ok(c)), key=lambda c: -(c.id or 0))
        return found[offset : offset + limit]

    async def record_reason_change(self, change: CaseReasonChange) -> None:
        self.history.append(change)

    async def reason_history(self, case_id: int) -> list[CaseReasonChange]:
        return [h for h in reversed(self.history) if h.case_id == case_id]
