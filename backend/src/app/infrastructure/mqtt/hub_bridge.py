"""
Połączenie ORDLY z brokerem MQTT, przez które rozmawia ORDLy Control Hub.

Jedno długo żyjące połączenie w tym samym procesie co reszta ORDLY.
Zerwane połączenie (restart Mosquitto, chwilowy problem) nie wywraca
aplikacji: most czeka i łączy się ponownie, a w tym czasie `publish`
zwraca False. Nic nie ginie, bo stan zdarzeń leży w bazie i po powrocie
Hub dostaje go w całości (`HubEventsService.handle_hub_status`).

ORDLY ogłasza też własną obecność na `ordly/backend/status` (retained,
z LWT "offline"): Hub odróżnia dzięki temu "broker działa, ale ORDLY
leży" od "wszystko w porządku" i miga wtedy niebieską jak przy braku MQTT.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

import aiomqtt
from loguru import logger

from app.core.config import HubMqttSettings

TOPIC_BACKEND_STATUS = "ordly/backend/status"

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]

#: Pierwsza przerwa po zerwanym połączeniu; potem rośnie do RECONNECT_MAX_SECONDS.
RECONNECT_MIN_SECONDS = 5.0
RECONNECT_MAX_SECONDS = 60.0


class MqttHubBridge:
    """Utrzymuje połączenie z brokerem, wysyła wiadomości i rozdziela przychodzące."""

    def __init__(self, settings: HubMqttSettings, client_id: str = "ordly-backend") -> None:
        self._settings = settings
        self._client_id = client_id
        self._client: aiomqtt.Client | None = None
        self._handlers: dict[str, MessageHandler] = {}
        self._connected = asyncio.Event()

    @property
    def connected(self) -> bool:
        """Czy most ma w tej chwili połączenie z brokerem."""
        return self._client is not None

    def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Rejestruje obsługę tematu (przed `run`). Treść musi być obiektem JSON."""
        self._handlers[topic] = handler

    async def wait_connected(self, within_seconds: float) -> bool:
        """Czeka na połączenie (dla testów i diagnostyki)."""
        try:
            await asyncio.wait_for(self._connected.wait(), within_seconds)
        except TimeoutError:
            return False
        return True

    async def publish(self, topic: str, payload: dict[str, Any], retain: bool = False) -> bool:
        """
        Wysyła wiadomość JSON z QoS 1.

        Returns:
            False, gdy nie ma połączenia z brokerem - wiadomość przepada,
            ale stan zdarzeń jest w bazie i Hub dostanie go po powrocie.
        """
        client = self._client
        if client is None:
            logger.debug("MQTT: brak połączenia, pomijam {}", topic)
            return False
        try:
            await client.publish(
                topic,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                qos=1,
                retain=retain,
            )
        except aiomqtt.MqttError as exc:
            logger.warning("MQTT: nie wysłano {}: {}", topic, exc)
            return False
        return True

    async def run(self, stop_event: asyncio.Event) -> None:
        """Pętla połączenia - działa do `stop_event`, łącząc się ponownie po awariach."""
        delay = RECONNECT_MIN_SECONDS
        stop_waiter = asyncio.create_task(stop_event.wait())
        try:
            while not stop_event.is_set():
                connection = asyncio.create_task(self._run_connection())
                await asyncio.wait(
                    {connection, stop_waiter}, return_when=asyncio.FIRST_COMPLETED
                )
                if not connection.done():
                    # Zamykanie aplikacji: "offline" od razu (LWT zadziałałby
                    # dopiero po 1,5 x keepalive), potem koniec czekania na wiadomości.
                    await self.publish(TOPIC_BACKEND_STATUS, {"online": False}, retain=True)
                    connection.cancel()
                    with suppress(asyncio.CancelledError, aiomqtt.MqttError):
                        await connection
                    break
                if self._connected.is_set():
                    # Połączenie działało - po jego zerwaniu zaczynamy od krótkiej przerwy.
                    delay = RECONNECT_MIN_SECONDS
                self._client = None
                self._connected.clear()
                exc = connection.exception()
                if exc is not None and not isinstance(exc, aiomqtt.MqttError):
                    raise exc
                logger.warning(
                    "MQTT: brak połączenia z {}:{} ({}). Ponowię za {:.0f} s",
                    self._settings.host,
                    self._settings.port,
                    exc or "rozłączono",
                    delay,
                )
                try:
                    await asyncio.wait_for(asyncio.shield(stop_waiter), timeout=delay)
                except TimeoutError:
                    delay = min(delay * 2, RECONNECT_MAX_SECONDS)
        finally:
            stop_waiter.cancel()
            self._client = None
            self._connected.clear()

    async def _run_connection(self) -> None:
        will = aiomqtt.Will(
            topic=TOPIC_BACKEND_STATUS, payload='{"online":false}', qos=1, retain=True
        )
        async with aiomqtt.Client(
            hostname=self._settings.host,
            port=self._settings.port,
            username=self._settings.user,
            password=self._settings.password.get_secret_value(),
            identifier=self._client_id,
            will=will,
            keepalive=30,
        ) as client:
            self._client = client
            logger.info(
                "MQTT: połączono z {}:{} jako {}",
                self._settings.host,
                self._settings.port,
                self._settings.user,
            )
            await client.publish(TOPIC_BACKEND_STATUS, '{"online":true}', qos=1, retain=True)
            for topic in self._handlers:
                await client.subscribe(topic, qos=1)
            self._connected.set()
            async for message in client.messages:
                await self._dispatch(str(message.topic), message.payload)

    async def _dispatch(self, topic: str, raw: Any) -> None:
        handler = self._handlers.get(topic)
        if handler is None:
            return
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes | bytearray) else str(raw)
            payload = json.loads(text)
        except (UnicodeDecodeError, ValueError):
            logger.warning("MQTT: niepoprawny JSON na {}: {!r}", topic, raw)
            return
        if not isinstance(payload, dict):
            logger.warning("MQTT: oczekiwano obiektu JSON na {}", topic)
            return
        await self._safe_call(lambda: handler(payload), topic)

    @staticmethod
    async def _safe_call(call: Callable[[], Awaitable[None]], context: str) -> None:
        # Błąd w obsłudze jednej wiadomości nie może zerwać połączenia z brokerem.
        try:
            await call()
        except Exception:
            logger.exception("MQTT: błąd obsługi ({})", context)
