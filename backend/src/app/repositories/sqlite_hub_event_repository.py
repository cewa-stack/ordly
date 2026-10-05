"""Repozytorium zdarzeń ORDLy Control Hub oparte o SQLite."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.hub_event_model import HubEventModel
from app.domain.entities.hub_event import REASON_ACKNOWLEDGED, HubEvent
from app.utils.time import utc_now


class SqliteHubEventRepository:
    """Zapisuje zdarzenia Huba i ich zamknięcie (OK na Hubie albo zmiana w ORDLY)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def open(
        self, source_key: str, type_: str, priority: str, data: dict[str, Any]
    ) -> HubEvent | None:
        """
        Zakłada nowe zdarzenie.

        Zwraca `None`, gdy zdarzenie z tym `source_key` już istnieje
        (aktywne albo zamknięte) - to samo zamówienie wykryte drugi raz
        nie może wrócić na Hub po tym, jak ktoś je potwierdził.
        """
        existing = await self._get_model_by_source_key(source_key)
        if existing is not None:
            return None
        model = HubEventModel(
            source_key=source_key,
            type=type_,
            priority=priority,
            data_json=json.dumps(data, ensure_ascii=False, default=str),
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_domain(model)

    async def reopen_or_open(
        self, source_key: str, type_: str, priority: str, data: dict[str, Any]
    ) -> HubEvent | None:
        """
        Jak `open`, ale zdarzenie zamknięte przez ORDLY (`resolved_at`)
        otwiera ponownie.

        Dla problemów z systemem: Allegro, które padło we wtorek i w środę,
        to dwa osobne problemy pod tym samym kluczem kanału. Zwraca `None`,
        gdy zdarzenie jest aktywne albo potwierdzone OK w tej samej serii
        awarii (`acked_at` bez `resolved_at`) - potwierdzony problem nie
        może wracać co minutę, dopóki kanał nie odpowie i nie padnie znowu.
        """
        existing = await self._get_model_by_source_key(source_key)
        if existing is None:
            return await self.open(source_key, type_, priority, data)
        if existing.resolved_at is None:
            return None
        existing.acked_at = None
        existing.resolved_at = None
        existing.resolve_reason = None
        existing.type = type_
        existing.priority = priority
        existing.data_json = json.dumps(data, ensure_ascii=False, default=str)
        # Ponowne otwarcie to nowe zdarzenie dla człowieka - "ile czeka" liczy się od teraz.
        existing.created_at = utc_now()
        await self._session.flush()
        return self._to_domain(existing)

    async def get(self, event_id: int) -> HubEvent | None:
        """Zwraca zdarzenie po numerze albo `None`."""
        model = await self._session.get(HubEventModel, event_id)
        return self._to_domain(model) if model is not None else None

    async def get_active(self, limit: int) -> list[HubEvent]:
        """Aktywne zdarzenia od najnowszego."""
        stmt = (
            select(HubEventModel)
            .where(HubEventModel.acked_at.is_(None), HubEventModel.resolved_at.is_(None))
            .order_by(HubEventModel.created_at.desc(), HubEventModel.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def count_active(self) -> int:
        """Liczba wszystkich aktywnych zdarzeń (także tych poza limitem listy)."""
        stmt = select(func.count(HubEventModel.id)).where(
            HubEventModel.acked_at.is_(None), HubEventModel.resolved_at.is_(None)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def get_active_by_source_prefix(
        self, prefix: str, include_acknowledged: bool = False
    ) -> list[HubEvent]:
        """
        Aktywne zdarzenia, których klucz źródła zaczyna się od `prefix`.

        `include_acknowledged` dokłada potwierdzone OK, ale jeszcze nie
        zamknięte przez ORDLY (trwająca seria awarii kanału).
        """
        stmt = select(HubEventModel).where(
            HubEventModel.resolved_at.is_(None),
            HubEventModel.source_key.startswith(prefix, autoescape=True),
        )
        if not include_acknowledged:
            stmt = stmt.where(HubEventModel.acked_at.is_(None))
        result = await self._session.execute(stmt)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def acknowledge(self, event_id: int) -> HubEvent | None:
        """
        Zamyka zdarzenie potwierdzone przyciskiem OK.

        Zwraca zamknięte zdarzenie albo `None`, gdy go nie ma lub już było
        zamknięte - podwójne naciśnięcie OK albo ponowione przez sieć
        potwierdzenie niczego nie psuje.
        """
        model = await self._session.get(HubEventModel, event_id)
        if model is None or model.acked_at is not None or model.resolved_at is not None:
            return None
        model.acked_at = utc_now()
        model.resolve_reason = REASON_ACKNOWLEDGED
        await self._session.flush()
        return self._to_domain(model)

    async def resolve_by_source_key(
        self, source_key: str, reason: str, include_acknowledged: bool = False
    ) -> HubEvent | None:
        """
        Zamyka aktywne zdarzenie, bo sprawa rozwiązała się w ORDLY.

        `include_acknowledged` domyka też zdarzenie już potwierdzone OK
        (koniec serii awarii - patrz `reopen_or_open`); zwrócone zdarzenie
        ma wtedy ustawione `acked_at`. Zwraca `None`, gdy nie było czego
        zamykać.
        """
        model = await self._get_model_by_source_key(source_key)
        if model is None or model.resolved_at is not None:
            return None
        if model.acked_at is not None and not include_acknowledged:
            return None
        model.resolved_at = utc_now()
        model.resolve_reason = reason
        await self._session.flush()
        return self._to_domain(model)

    async def _get_model_by_source_key(self, source_key: str) -> HubEventModel | None:
        stmt = select(HubEventModel).where(HubEventModel.source_key == source_key)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _to_domain(model: HubEventModel) -> HubEvent:
        try:
            data = json.loads(model.data_json or "{}")
        except ValueError:
            data = {}
        return HubEvent(
            id=model.id,
            source_key=model.source_key,
            type=model.type,
            priority=model.priority,
            created_at=model.created_at,
            data=data if isinstance(data, dict) else {},
            acked_at=model.acked_at,
            resolved_at=model.resolved_at,
            resolve_reason=model.resolve_reason,
        )
