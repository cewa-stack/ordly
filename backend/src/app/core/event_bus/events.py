"""
Definicje zdarzeń emitowanych przez Event Bus.

Każde zdarzenie jest niemutowalnym obiektem danych (dataclass frozen)
reprezentującym fakt, który już się wydarzył w systemie.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.allegro_lokalnie_event import AllegroLokalnieEvent
from app.domain.entities.dispute_notice import DisputeNotice
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Bazowa klasa dla wszystkich zdarzeń domenowych."""

    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class OrderCreated(DomainEvent):
    """Emitowane, gdy scheduler wykryje nowe, wcześniej nieznane zamówienie."""

    order: Order


@dataclass(frozen=True, slots=True)
class OrderUpdated(DomainEvent):
    """Emitowane, gdy status znanego zamówienia się zmienił."""

    order: Order


@dataclass(frozen=True, slots=True)
class OrderCancelled(DomainEvent):
    """Emitowane, gdy status znanego zamówienia zmienił się na anulowane."""

    order: Order


@dataclass(frozen=True, slots=True)
class OrderPackingStarted(DomainEvent):
    """
    Emitowane, gdy status realizacji znanego zamówienia przeszedł na
    etap pakowania (PROCESSING) - wyzwalacz SMS do klienta.
    """

    order: Order


@dataclass(frozen=True, slots=True)
class OrderReturnCreated(DomainEvent):
    """Emitowane, gdy synchronizacja wykryje nowy zwrot produktów z zamówienia."""

    order_return: OrderReturn


@dataclass(frozen=True, slots=True)
class AllegroLokalnieEventDetected(DomainEvent):
    """
    Emitowane, gdy synchronizacja skrzynki wykryje nowe powiadomienie
    z Allegro Lokalnie.

    Allegro Lokalnie nie ma API, więc to jedyny sposób, w jaki ORDLY
    dowiaduje się o tamtejszej sprzedaży. Zdarzenie jest publikowane raz
    na mail - klucz `Message-ID` jest kluczem głównym tabeli
    `mail_messages`, więc ponowny skan tego samego zakresu dat nie
    wygeneruje duplikatu powiadomienia.
    """

    event: AllegroLokalnieEvent


@dataclass(frozen=True, slots=True)
class DisputeNoticeDetected(DomainEvent):
    """
    Emitowane, gdy skrzynka wykryje mail o ROZPOCZĘTEJ dyskusji na Allegro.pl.

    Allegro.pl ma API, ale ORDLY odpytuje `/sale/issues` dopiero przy
    otwarciu ekranu Dyskusji - bez tego zdarzenia o nowej dyskusji
    dowiadywałbyś się, gdy sam zajrzysz. W mailu jest też termin
    odpowiedzi, którego API nie zwraca.

    Publikowane raz na mail: `Message-ID` jest kluczem głównym tabeli
    `mail_messages`, więc ponowny skan nie wygeneruje duplikatu.
    """

    notice: DisputeNotice


@dataclass(frozen=True, slots=True)
class ShipmentChecked(DomainEvent):
    """Emitowane po sprawdzeniu statusu przesyłki na żądanie użytkownika."""

    order_external_id: str
    status: str | None


@dataclass(frozen=True, slots=True)
class NotificationSent(DomainEvent):
    """Emitowane po pomyślnym wysłaniu powiadomienia Telegram."""

    order_external_id: str


@dataclass(frozen=True, slots=True)
class PluginLoaded(DomainEvent):
    """Emitowane przy starcie aplikacji dla każdego zarejestrowanego pluginu."""

    marketplace_code: str


@dataclass(frozen=True, slots=True)
class BackupCreated(DomainEvent):
    """Emitowane po pomyślnym utworzeniu kopii zapasowej bazy danych."""

    backup_path: str


@dataclass(frozen=True, slots=True)
class LowStockDetected(DomainEvent):
    """Emitowane, gdy produkt magazynowy osiągnie minimalny stan po synchronizacji."""

    sku: str
    name: str
    stock: int
    min_stock: int


@dataclass(frozen=True, slots=True)
class SyncStarted(DomainEvent):
    """Emitowane na początku każdej synchronizacji zamówień."""


@dataclass(frozen=True, slots=True)
class SyncFinished(DomainEvent):
    """Emitowane po zakończeniu synchronizacji zamówień."""

    new_orders_count: int
    checked_orders_count: int
