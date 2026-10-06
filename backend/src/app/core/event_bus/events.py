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
from app.domain.entities.olx_event import OlxEvent
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.domain.entities.wholesale_parcel import WholesaleParcelNotice
from app.domain.returns import ReturnStatusChange


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
    """
    Emitowane, gdy status znanego zamówienia zmienił się na anulowane.

    `notify=False`, gdy użytkownik zamknął już zamówienie ręcznie
    w aplikacji (Zrealizowane / Anulowane) - zdarzenie trafia do audytu,
    ale bez powiadomienia (app/domain/order_status.py).
    """

    order: Order
    notify: bool = True


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
class ReturnStatusChanged(DomainEvent):
    """
    Emitowane, gdy synchronizacja utrwali nowy status znanego zwrotu.

    Subskrybent zapisuje zmianę w audycie (tabela events), dzięki czemu
    w logach aplikacji widać, kiedy i skąd zwrot został zamknięty.
    """

    change: ReturnStatusChange


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
class OlxEventDetected(DomainEvent):
    """
    Emitowane, gdy synchronizacja skrzynki wykryje nowe powiadomienie
    z OLX.

    Bliźniacze wobec `AllegroLokalnieEventDetected` i z tego samego
    powodu: OLX nie ma samoobsługowego API dla sprzedawców, więc mail
    jest jedynym sygnałem, że cokolwiek się tam wydarzyło. Zdarzenie
    jest publikowane raz na mail - `Message-ID` jest kluczem głównym
    tabeli `mail_messages`, więc ponowny skan tego samego zakresu dat
    nie wygeneruje duplikatu powiadomienia.
    """

    event: OlxEvent


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
class SyncStarted(DomainEvent):
    """Emitowane na początku każdej synchronizacji zamówień."""


@dataclass(frozen=True, slots=True)
class SyncFinished(DomainEvent):
    """Emitowane po zakończeniu synchronizacji zamówień."""

    new_orders_count: int
    checked_orders_count: int


@dataclass(frozen=True, slots=True)
class ReturnRefunded(DomainEvent):
    """
    Emitowane, gdy zwrot klienta wszedł w status "pieniądze oddane"
    (albo został pierwszy raz zobaczony już w takim statusie) - wyzwalacz
    zapisu w rejestrze anulowań i zwrotów (app/domain/customer_cases.py).
    """

    order_return: OrderReturn


@dataclass(frozen=True, slots=True)
class OrderAppStatusChanged(DomainEvent):
    """
    Emitowane po RĘCZNEJ zmianie statusu aplikacyjnego zamówienia
    (po zatwierdzeniu zapisu). `new_status` = status widoczny po zmianie.
    """

    order: Order
    previous_status: str | None
    new_status: str | None


@dataclass(frozen=True, slots=True)
class WholesaleParcelShipped(DomainEvent):
    """
    InPost potwierdził nadanie paczki od hurtowni (F.H.P. MAIK-POL) -
    jednorazowy alert informacyjny na Control Hub i telefon ([FEAT-MAIL]).
    Wysyłane najwyżej raz na mail (`processed_parcel_mails`).
    """

    notice: WholesaleParcelNotice
