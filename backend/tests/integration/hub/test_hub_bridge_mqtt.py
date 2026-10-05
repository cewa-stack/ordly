"""
Most MQTT na prawdziwym protokole: aiomqtt (ORDLY) i drugi klient
udający Hub rozmawiają po TCP z brokerem MQTT 3.1.1 (`MiniMqttBroker`).

Sprawdza to, czego nie pokaże zapisujący publisher: logowanie hasłem,
LWT i retained `ordly/backend/status`, odbiór retained statusu Huba
zaraz po połączeniu (to on wyzwala snapshot po restarcie ORDLY),
potwierdzenie OK z Huba aż do bazy i odporność na śmieci w wiadomości.

aiomqtt potrzebuje pętli z `add_reader` - na Windows (środowisko
deweloperskie) domyślna pętla Proactor jej nie ma, dlatego scenariusze
uruchamiamy na SelectorEventLoop. Na Raspberry Pi to domyślna pętla.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import aiomqtt
from pydantic import SecretStr

from app.core.config import HubMqttSettings
from app.domain.entities.order import Order
from app.infrastructure.mqtt.hub_bridge import TOPIC_BACKEND_STATUS, MqttHubBridge
from app.repositories.sqlite_hub_event_repository import SqliteHubEventRepository
from app.repositories.sqlite_order_repository import SqliteOrderRepository
from app.services.hub_events_service import (
    TOPIC_EVENT_NEW,
    TOPIC_EVENT_SNAPSHOT,
    TOPIC_HUB_ACK,
    TOPIC_HUB_STATUS,
    HubEventsService,
)
from app.services.hub_history_service import (
    TOPIC_HISTORY_DAY,
    TOPIC_HISTORY_GET,
    HubHistoryService,
)
from app.services.hub_wholesale_service import (
    TOPIC_WHOLESALE_RESULT,
    TOPIC_WHOLESALE_SEND,
    HubWholesaleService,
)
from tests.fakes.mini_mqtt_broker import MiniMqttBroker
from tests.integration.hub.conftest import make_database

USERS = {"ordly": "haslo-ordly", "hub": "haslo-hub"}


def _run(scenario: Callable[[], Awaitable[None]]) -> None:
    asyncio.run(scenario(), loop_factory=asyncio.SelectorEventLoop)


def _settings(port: int, password: str = "haslo-ordly") -> HubMqttSettings:
    return HubMqttSettings(
        MQTT_HOST="127.0.0.1",
        MQTT_PORT=port,
        MQTT_USER="ordly",
        MQTT_PASSWORD=SecretStr(password),
    )


async def _eventually(check: Callable[[], Awaitable[bool]]) -> None:
    """Sprawdza warunek co 50 ms, najwyżej przez 5 s."""
    for _ in range(100):
        if await check():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("warunek nie spełnił się w 5 s")


def test_hub_po_polaczeniu_dostaje_snapshot_a_ok_trafia_do_bazy(
    tmp_path: Path, sample_order: Order
) -> None:
    async def scenario() -> None:
        engine, session_scope = await make_database(tmp_path / "hub.db")
        async with MiniMqttBroker(USERS) as broker:
            bridge = MqttHubBridge(_settings(broker.port))
            hub_service = HubEventsService(
                session_scope_factory=session_scope, publisher=bridge
            )
            bridge.subscribe(TOPIC_HUB_ACK, hub_service.handle_ack)
            bridge.subscribe(TOPIC_HUB_STATUS, hub_service.handle_hub_status)
            stop = asyncio.Event()

            # Zamówienie przyszło, zanim Hub i ORDLY w ogóle się połączyły.
            await hub_service.on_order_created(sample_order)

            # Hub był online wcześniej: jego status jest retained u brokera.
            async with aiomqtt.Client(
                "127.0.0.1",
                broker.port,
                username="hub",
                password="haslo-hub",
                identifier="hub",
            ) as hub:
                await hub.subscribe("ordly/#")
                await hub.publish(
                    TOPIC_HUB_STATUS,
                    '{"online":true,"fw_version":"0.4.0"}',
                    qos=1,
                    retain=True,
                )

                task = asyncio.create_task(bridge.run(stop))
                assert await bridge.wait_connected(5)

                received: dict[str, Any] = {}

                async def _read() -> None:
                    async for message in hub.messages:
                        if str(message.topic) == TOPIC_EVENT_SNAPSHOT:
                            received.update(json.loads(message.payload))
                            return

                await asyncio.wait_for(_read(), 5)
                assert received["total"] == 1
                assert received["events"][0]["id"] == "evt_1"
                assert broker.retained(TOPIC_BACKEND_STATUS) == b'{"online":true}'

                # Śmieci nie zrywają połączenia, a OK z Huba trafia do bazy.
                await hub.publish(TOPIC_HUB_ACK, b"\xff nie-json", qos=1)
                await hub.publish(TOPIC_HUB_ACK, '{"event_id":"evt_1"}', qos=1)

                async def _acked() -> bool:
                    async with session_scope() as session:
                        return await SqliteHubEventRepository(session).count_active() == 0

                await _eventually(_acked)
                assert bridge.connected

            stop.set()
            await asyncio.wait_for(task, 5)
            assert broker.retained(TOPIC_BACKEND_STATUS) == b'{"online":false}'
        await engine.dispose()

    _run(scenario)


def test_nowe_zdarzenie_idzie_na_ordly_events_new_jako_utf8(
    tmp_path: Path, sample_order: Order
) -> None:
    async def scenario() -> None:
        engine, session_scope = await make_database(tmp_path / "hub.db")
        async with MiniMqttBroker(USERS) as broker:
            bridge = MqttHubBridge(_settings(broker.port))
            hub_service = HubEventsService(
                session_scope_factory=session_scope, publisher=bridge
            )
            stop = asyncio.Event()
            task = asyncio.create_task(bridge.run(stop))
            assert await bridge.wait_connected(5)

            await hub_service.on_order_created(sample_order)

            [raw] = await broker.wait_for(TOPIC_EVENT_NEW)
            message = json.loads(raw.decode("utf-8"))
            assert message["id"] == "evt_1"
            assert message["data"]["summary"] == "Kubek ceramiczny x2"

            stop.set()
            await asyncio.wait_for(task, 5)
        await engine.dispose()

    _run(scenario)


def test_zle_haslo_nie_wywraca_ordly() -> None:
    async def scenario() -> None:
        async with MiniMqttBroker(USERS) as broker:
            bridge = MqttHubBridge(_settings(broker.port, password="zle"))
            stop = asyncio.Event()
            task = asyncio.create_task(bridge.run(stop))

            assert not await bridge.wait_connected(1)
            assert await bridge.publish("ordly/test", {"x": 1}) is False

            stop.set()
            await asyncio.wait_for(task, 10)

    _run(scenario)


def test_hub_prosi_o_historie_i_dostaje_dzien(tmp_path: Path, sample_order: Order) -> None:
    async def scenario() -> None:
        engine, session_scope = await make_database(tmp_path / "hub.db")
        async with session_scope() as session:
            await SqliteOrderRepository(session).save(
                sample_order
            )  # 1.07.2026, 12:00 w Polsce
        async with MiniMqttBroker(USERS) as broker:
            bridge = MqttHubBridge(_settings(broker.port))
            history = HubHistoryService(session_scope_factory=session_scope, publisher=bridge)
            bridge.subscribe(TOPIC_HISTORY_GET, history.handle_request)
            stop = asyncio.Event()
            task = asyncio.create_task(bridge.run(stop))
            assert await bridge.wait_connected(5)

            async with aiomqtt.Client(
                "127.0.0.1",
                broker.port,
                username="hub",
                password="haslo-hub",
                identifier="hub",
            ) as hub:
                await hub.subscribe(TOPIC_HISTORY_DAY, qos=1)
                await hub.publish(TOPIC_HISTORY_GET, '{"date":"2026-07-01","page":0}', qos=1)

                async def _read() -> dict[str, Any]:
                    async for message in hub.messages:
                        return dict(json.loads(message.payload))
                    raise AssertionError("brak odpowiedzi")

                day = await asyncio.wait_for(_read(), 5)

            assert day["date"] == "2026-07-01"
            assert day["orders_count"] == 1
            assert day["rows"][0]["time"] == "12:00"
            assert day["rows"][0]["summary"] == "Kubek ceramiczny x2"

            stop.set()
            await asyncio.wait_for(task, 5)
        await engine.dispose()

    _run(scenario)


def test_hub_zamawia_w_hurtowni_przez_mqtt(tmp_path: Path) -> None:
    """Prośba z Huba po MQTT -> mail wychodzi raz, Hub dostaje wynik; powtórka nic nie wysyła."""
    sent: list[tuple[str, str, str]] = []

    class _Mailer:
        async def send(self, to: str, subject: str, body: str) -> None:
            sent.append((to, subject, body))

    async def scenario() -> None:
        engine, session_scope = await make_database(tmp_path / "hub.db")
        async with MiniMqttBroker(USERS) as broker:
            bridge = MqttHubBridge(_settings(broker.port))
            wholesale = HubWholesaleService(
                session_scope_factory=session_scope,
                mailer_factory=_Mailer,
                publisher=bridge,
                test_mode=False,
                test_recipient="sklep@example.com",
            )
            version = await wholesale.save_catalog(
                {
                    "wholesalers": [
                        {
                            "id": "w-1",
                            "name": "Hurt-Pol",
                            "email": "zamowienia@hurtpol.example",
                            "items": [{"name": "Kubek", "quantity": 24}],
                        }
                    ],
                    "templates": [
                        {
                            "id": "t",
                            "name": "Std",
                            "subject": "Zamówienie - {produkty}",
                            "body": "{lista_pozycji}",
                            "inquirySubject": "Zapytanie",
                            "inquiryBody": "",
                            "isDefault": True,
                        }
                    ],
                }
            )
            bridge.subscribe(TOPIC_WHOLESALE_SEND, wholesale.handle_send)
            stop = asyncio.Event()
            task = asyncio.create_task(bridge.run(stop))
            assert await bridge.wait_connected(5)

            request = json.dumps(
                {"request_id": "r-1", "version": version, "wholesaler_id": "w-1", "items": [0]}
            )
            async with aiomqtt.Client(
                "127.0.0.1",
                broker.port,
                username="hub",
                password="haslo-hub",
                identifier="hub",
            ) as hub:
                await hub.subscribe(TOPIC_WHOLESALE_RESULT, qos=1)
                await hub.publish(TOPIC_WHOLESALE_SEND, request, qos=1)
                await hub.publish(TOPIC_WHOLESALE_SEND, request, qos=1)

                results: list[dict[str, Any]] = []

                async def _read() -> None:
                    async for message in hub.messages:
                        results.append(json.loads(message.payload))
                        if len(results) == 2:
                            return

                await asyncio.wait_for(_read(), 5)

            assert [r["status"] for r in results] == ["sent", "already_sent"]
            assert sent == [
                (
                    "zamowienia@hurtpol.example",
                    "Zamówienie - Kubek",
                    "- Kubek - ilość: 24 szt.",
                )
            ]

            stop.set()
            await asyncio.wait_for(task, 5)
        await engine.dispose()

    _run(scenario)
