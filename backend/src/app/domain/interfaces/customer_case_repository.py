"""Abstrakcyjny kontrakt rejestru anulowań i zwrotów pieniędzy."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.customer_cases import CaseFilters, CaseReasonChange, CustomerCase


class CustomerCaseRepository(ABC):
    """Dostęp do rekordów `customer_cases`, niezależny od bazy danych."""

    @abstractmethod
    async def get_by_order(self, marketplace: str, order_external_id: str) -> CustomerCase | None:
        """Rekord danego zamówienia albo None."""

    @abstractmethod
    async def get(self, case_id: int) -> CustomerCase | None:
        """Rekord po identyfikatorze albo None."""

    @abstractmethod
    async def add(self, case: CustomerCase) -> CustomerCase:
        """Zapisuje nowy rekord i zwraca go z nadanym `id`."""

    @abstractmethod
    async def update(self, case: CustomerCase) -> CustomerCase:
        """Nadpisuje istniejący rekord (po `id`) i zwraca go po zapisie."""

    @abstractmethod
    async def find(self, filters: CaseFilters, limit: int, offset: int = 0) -> list[CustomerCase]:
        """Rekordy spełniające filtry, od najnowszego zdarzenia."""

    @abstractmethod
    async def record_reason_change(self, change: CaseReasonChange) -> None:
        """Dopisuje wpis do historii powodu."""

    @abstractmethod
    async def reason_history(self, case_id: int) -> list[CaseReasonChange]:
        """Historia powodu rekordu, od najnowszej zmiany."""
