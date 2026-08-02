"""
Prosty, wewnątrzprocesowy Event Bus (publish/subscribe).

Celowo implementowany in-memory (bez Redis/RabbitMQ) - projekt działa
w jednym procesie na Raspberry Pi, więc rozproszona kolejka wiadomości
byłaby niepotrzebną złożonością.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TypeVar

from loguru import logger

from app.core.event_bus.events import DomainEvent

TEvent = TypeVar("TEvent", bound=DomainEvent)
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    """Rejestr subskrybentów i mechanizm publikacji zdarzeń domenowych."""

    def __init__(self) -> None:
        self._subscribers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[TEvent], handler: EventHandler) -> None:
        """
        Rejestruje handler wywoływany przy publikacji zdarzenia danego typu.

        Args:
            event_type: Klasa zdarzenia (np. OrderCreated).
            handler: Asynchroniczna funkcja przyjmująca zdarzenie.
        """
        self._subscribers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """
        Publikuje zdarzenie do wszystkich zarejestrowanych subskrybentów.

        Args:
            event: Instancja zdarzenia do opublikowania.
        """
        handlers = self._subscribers.get(type(event), [])
        logger.debug(
            "Publikacja zdarzenia {} do {} subskrybent(ów)",
            type(event).__name__,
            len(handlers),
        )
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("Błąd w subskrybencie zdarzenia {}", type(event).__name__)
