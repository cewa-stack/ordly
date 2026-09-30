"""
Pozycja z Notion "Brak powiązania zmiany statusu zwrotu z jego
automatycznym zakończeniem" - na prawdziwej bazie SQLite.

- „Anulowane” (CANCELLED) z Allegro jednoznacznie zamyka zwrot,
- zakończony zwrot nie wraca po kolejnej synchronizacji (nieaktualny,
  otwarty status po zamkniętym jest odrzucany),
- każda zmiana statusu trafia do historii (tabela events): kiedy, skąd,
  z czego na co,
- pozostałe statusy nie są zamykane przedwcześnie.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.schemas import return_out
from app.core.event_bus.bus import EventBus
from app.database.models.event_model import EventModel
from app.event_subscriptions import register_event_subscriptions
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.repositories.sqlite_return_repository import SqliteReturnRepository
from app.services.sync_orders_service import SyncOrdersService


def _container(session, bus: EventBus):
    @asynccontextmanager
    async def session_scope():
        yield session
        await session.commit()

    return SimpleNamespace(event_bus=bus, session_scope=session_scope)


async def _sync(plugin, session, bus: EventBus):
    service = SyncOrdersService(
        plugin, SqliteOrderRepository(session), bus, SqliteReturnRepository(session)
    )
    result = await service.sync_new_orders()
    await session.commit()
    await service.publish_sync_events(result)
    return result


async def _history(session) -> list[dict]:
    rows = await session.execute(
        select(EventModel)
        .where(EventModel.event_type == "ReturnStatusChanged")
        .order_by(EventModel.id)
    )
    return [json.loads(m.payload_json) for m in rows.scalars().all()]


async def _status(session, external_id: str = "RETURN-001") -> str | None:
    return await SqliteReturnRepository(session).get_status("allegro", external_id)


@pytest.fixture
def bus(in_memory_session) -> EventBus:
    event_bus = EventBus()
    register_event_subscriptions(_container(in_memory_session, event_bus))  # type: ignore[arg-type]
    return event_bus


class TestAnulowanyZwrot:
    @pytest.mark.asyncio
    async def test_anulowany_na_allegro_zamyka_zwrot_i_zostawia_historie(
        self, in_memory_session, fake_marketplace_plugin, sample_return, bus
    ):
        await SqliteReturnRepository(in_memory_session).save(sample_return)  # CREATED
        await in_memory_session.commit()
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status="CANCELLED")]

        result = await _sync(fake_marketplace_plugin, in_memory_session, bus)

        assert await _status(in_memory_session) == "CANCELLED"
        [record] = await SqliteReturnRepository(in_memory_session).get_recent()
        assert return_out(record).requires_action is False
        assert return_out(record).status_label == "Anulowany"
        [change] = result.return_status_changes
        assert change.closes_return is True
        [entry] = await _history(in_memory_session)
        assert entry["return_external_id"] == "RETURN-001"
        assert entry["previous_status"] == "CREATED"
        assert entry["new_status"] == "CANCELLED"
        assert entry["closed"] is True
        assert entry["source"] == "allegro"
        assert entry["changed_at"]

    @pytest.mark.asyncio
    async def test_zakonczony_nie_wraca_po_kolejnej_synchronizacji(
        self, in_memory_session, fake_marketplace_plugin, sample_return, bus
    ):
        await SqliteReturnRepository(in_memory_session).save(sample_return)
        await in_memory_session.commit()
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status="CANCELLED")]
        await _sync(fake_marketplace_plugin, in_memory_session, bus)

        # Nieaktualna odpowiedź Allegro: znowu CREATED.
        fake_marketplace_plugin.returns_to_return = [sample_return]
        result = await _sync(fake_marketplace_plugin, in_memory_session, bus)
        # Restart usługi: nowy serwis, ta sama baza, ta sama odpowiedź.
        await _sync(fake_marketplace_plugin, in_memory_session, bus)

        assert await _status(in_memory_session) == "CANCELLED"
        assert result.return_status_changes == ()
        assert result.new_returns == ()
        assert len(await _history(in_memory_session)) == 1

    @pytest.mark.asyncio
    async def test_zmiany_miedzy_zamknietymi_sa_zapisywane(
        self, in_memory_session, fake_marketplace_plugin, sample_return, bus
    ):
        await SqliteReturnRepository(in_memory_session).save(
            replace(sample_return, status="FINISHED")
        )
        await in_memory_session.commit()
        fake_marketplace_plugin.returns_to_return = [
            replace(sample_return, status="COMMISSION_REFUNDED")
        ]

        await _sync(fake_marketplace_plugin, in_memory_session, bus)

        assert await _status(in_memory_session) == "COMMISSION_REFUNDED"
        [entry] = await _history(in_memory_session)
        assert entry["closed"] is False  # był już zamknięty wcześniej

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "open_status", ["DISPATCHED", "IN_TRANSIT", "DELIVERED", "WAREHOUSE_VERIFICATION"]
    )
    async def test_pozostale_statusy_nie_zamykaja_przedwczesnie(
        self, open_status, in_memory_session, fake_marketplace_plugin, sample_return, bus
    ):
        await SqliteReturnRepository(in_memory_session).save(sample_return)
        await in_memory_session.commit()
        fake_marketplace_plugin.returns_to_return = [replace(sample_return, status=open_status)]

        await _sync(fake_marketplace_plugin, in_memory_session, bus)

        assert await _status(in_memory_session) == open_status
        [record] = await SqliteReturnRepository(in_memory_session).get_recent()
        assert return_out(record).requires_action is True
        [entry] = await _history(in_memory_session)
        assert entry["closed"] is False
