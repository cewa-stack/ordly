"""
Status aplikacyjny zamówienia i reguła priorytetu wobec statusu Allegro.

ORDLY pokazuje każde zamówienie w jednym z czterech statusów
aplikacyjnych: **Nowe**, **W realizacji**, **Zrealizowane**, **Anulowane**.

Bez ręcznej zmiany status aplikacyjny wynika wprost z danych Allegro
(`allegro_app_status`). Użytkownik może go jednak ustawić ręcznie
w aplikacji - bez zmiany czegokolwiek na Allegro. Wtedy obowiązuje reguła
priorytetu (decyzja użytkownika z 2026-10-04, wariant B):

1. Ręczny status wygrywa ze statusem Allegro.
2. Dopóki Allegro nie zmieni stanu zamówienia od chwili ręcznej zmiany,
   nic go nie rusza - synchronizacja, która zwraca ten sam (albo
   wcześniejszy) status, niczego nie nadpisuje.
3. Uzgodnienie z Allegro następuje automatycznie wyłącznie "do przodu":
   ręczne "Nowe" / "W realizacji" ustępuje, gdy Allegro przejdzie dalej
   (np. ręcznie "W realizacji", a Allegro podaje "wysłane" -> status
   staje się "Zrealizowane").
4. "Zrealizowane" i "Anulowane" są końcowe - Allegro nigdy nie przywraca
   takiego zamówienia do nieobsłużonych. Jedyny wyjątek (decyzja D2-a):
   zamówienie oznaczone ręcznie jako "Zrealizowane", które Allegro potem
   anuluje, staje się "Anulowane" - ale bez powiadomienia.
5. Ręczne cofnięcie do statusu Allegro to osobna akcja ("Przywróć status
   z Allegro").

Do tego, żeby rozpoznać "Allegro zmieniło stan od ręcznej zmiany",
zapisujemy przy ręcznej zmianie `basis` - status aplikacyjny wynikający
z Allegro w tamtej chwili. Cała reguła jest czystą funkcją danych
zamówienia, więc działa tak samo po odświeżeniu aplikacji, restarcie bota
i każdej kolejnej synchronizacji - niezależnie od tego, która ścieżka
(synchronizacja, wykrycie numeru przesyłki, /tracking) zmieniła dane.

Etapy realizacji z Allegro (`fulfillment_status`) i oparte na nich
automatyzacje (SMS o pakowaniu, przypomnienie 20:00, czyszczenie 02:00)
działają dalej na swoich danych - status aplikacyjny jedynie wyłącza
z nich zamówienia, które użytkownik uznał za zamknięte.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.fulfillment import (
    FULFILLMENT_NEW,
    FULFILLMENT_PICKED_UP,
    FULFILLMENT_PROCESSING,
    FULFILLMENT_READY_FOR_PICKUP,
    FULFILLMENT_READY_FOR_SHIPMENT,
    FULFILLMENT_RETURNED,
    FULFILLMENT_SENT,
    FULFILLMENT_SUSPENDED,
    awaits_shipment,
    is_cancelled_order,
    requires_packing,
)

APP_STATUS_NEW = "NEW"
APP_STATUS_IN_PROGRESS = "IN_PROGRESS"
APP_STATUS_DONE = "DONE"
APP_STATUS_CANCELLED = "CANCELLED"

#: Wszystkie statusy aplikacyjne w kolejności obsługi.
APP_STATUSES: tuple[str, ...] = (
    APP_STATUS_NEW,
    APP_STATUS_IN_PROGRESS,
    APP_STATUS_DONE,
    APP_STATUS_CANCELLED,
)

#: Nazwy dla użytkownika - dokładnie jak w notatce z Notion.
APP_STATUS_LABELS: dict[str, str] = {
    APP_STATUS_NEW: "Nowe",
    APP_STATUS_IN_PROGRESS: "W realizacji",
    APP_STATUS_DONE: "Zrealizowane",
    APP_STATUS_CANCELLED: "Anulowane",
}

#: Statusy, w których zamówienie wymaga jeszcze obsługi.
OPEN_APP_STATUSES = frozenset({APP_STATUS_NEW, APP_STATUS_IN_PROGRESS})
#: Statusy końcowe - zamówienie nie wraca z nich do nieobsłużonych.
CLOSED_APP_STATUSES = frozenset({APP_STATUS_DONE, APP_STATUS_CANCELLED})

#: Pozycja na osi obsługi - do uzgadniania "tylko do przodu".
_RANK: dict[str, int] = {
    APP_STATUS_NEW: 0,
    APP_STATUS_IN_PROGRESS: 1,
    APP_STATUS_DONE: 2,
    APP_STATUS_CANCELLED: 2,
}

#: Źródło wpisu w historii zmian statusu aplikacyjnego.
APP_STATUS_SOURCE_MANUAL = "manual"
APP_STATUS_SOURCE_RESTORE = "restore_allegro"

_DONE_FULFILLMENT = frozenset(
    {FULFILLMENT_SENT, FULFILLMENT_PICKED_UP, FULFILLMENT_READY_FOR_PICKUP, FULFILLMENT_RETURNED}
)
_IN_PROGRESS_FULFILLMENT = frozenset(
    {FULFILLMENT_PROCESSING, FULFILLMENT_READY_FOR_SHIPMENT, FULFILLMENT_SUSPENDED}
)


@dataclass(frozen=True, slots=True)
class OrderStatusChange:
    """
    Wpis historii statusu aplikacyjnego: kiedy, skąd, z czego na co.

    `previous_status` / `new_status` to status WIDOCZNY dla użytkownika
    przed i po zmianie (None = "Brak danych").
    """

    marketplace: str
    order_external_id: str
    previous_status: str | None
    new_status: str | None
    source: str
    changed_at: datetime


class OrderStatusFields(Protocol):
    """Minimum danych zamówienia potrzebne regułom statusu aplikacyjnego."""

    @property
    def status(self) -> str: ...

    @property
    def fulfillment_status(self) -> str | None: ...

    @property
    def tracking_number(self) -> str | None: ...

    @property
    def app_status(self) -> str | None: ...

    @property
    def app_status_basis(self) -> str | None: ...


def is_valid_app_status(value: str) -> bool:
    """Czy wartość jest jednym z czterech statusów aplikacyjnych."""
    return value in APP_STATUSES


def app_status_label(value: str | None) -> str:
    """Nazwa statusu dla człowieka; brak statusu = "Brak danych"."""
    if value is None:
        return "Brak danych"
    return APP_STATUS_LABELS.get(value, value)


def allegro_app_status(
    status: str | None, fulfillment_status: str | None, tracking_number: str | None
) -> str | None:
    """
    Status aplikacyjny wynikający z samych danych Allegro.

    - anulowane (status płatności albo etap) -> Anulowane;
    - wysłane / odebrane / do odbioru / zwrócone albo wykryty numer
      przesyłki -> Zrealizowane;
    - NEW -> Nowe;
    - PROCESSING / READY_FOR_SHIPMENT / SUSPENDED -> W realizacji;
    - etap nieznany (NULL) -> None (Allegro jeszcze go nie potwierdziło).
    """
    if is_cancelled_order(status, fulfillment_status):
        return APP_STATUS_CANCELLED
    stage = fulfillment_status.upper() if fulfillment_status else None
    if tracking_number or stage in _DONE_FULFILLMENT:
        return APP_STATUS_DONE
    if stage == FULFILLMENT_NEW:
        return APP_STATUS_NEW
    if stage in _IN_PROGRESS_FULFILLMENT:
        return APP_STATUS_IN_PROGRESS
    return None


def resolve_app_status(manual: str | None, basis: str | None, derived: str | None) -> str | None:
    """
    Reguła priorytetu (patrz docstring modułu).

    Args:
        manual: Status ustawiony ręcznie w aplikacji (None = brak).
        basis: Status z Allegro w chwili ręcznej zmiany.
        derived: Status z Allegro teraz.
    """
    if manual is None:
        return derived
    if derived == basis:
        return manual
    # Allegro zmieniło stan od ręcznej zmiany - uzgadniamy tylko do przodu.
    if manual == APP_STATUS_DONE:
        return APP_STATUS_CANCELLED if derived == APP_STATUS_CANCELLED else APP_STATUS_DONE
    if manual == APP_STATUS_CANCELLED:
        return APP_STATUS_CANCELLED
    if derived is not None and _RANK[derived] > _RANK.get(manual, 0):
        return derived
    return manual


def effective_app_status(order: OrderStatusFields) -> str | None:
    """Status aplikacyjny, który widzi użytkownik."""
    derived = allegro_app_status(order.status, order.fulfillment_status, order.tracking_number)
    return resolve_app_status(order.app_status, order.app_status_basis, derived)


def is_manual_in_force(order: OrderStatusFields) -> bool:
    """
    Czy obowiązuje ręczny status - czyli ręczna zmiana nie została jeszcze
    uzgodniona z nowszym stanem Allegro. To ona decyduje o oznaczeniu
    "zmieniono ręcznie" w interfejsie.
    """
    return order.app_status is not None and effective_app_status(order) == order.app_status


def is_closed_in_app(order: OrderStatusFields) -> bool:
    """
    Czy użytkownik ręcznie zamknął zamówienie (Zrealizowane / Anulowane).

    Takie zamówienie nie generuje już żadnych powiadomień: ani o
    anulowaniu z Allegro, ani SMS-a o pakowaniu, ani przypomnień.
    """
    return is_manual_in_force(order) and order.app_status in CLOSED_APP_STATUSES


def app_status_display(order: OrderStatusFields) -> str:
    """
    Status do wyświetlenia w bocie: nazwa statusu aplikacyjnego i - gdy
    obowiązuje ręczna zmiana - jasna informacja, że zmieniono go w aplikacji.
    """
    label = app_status_label(effective_app_status(order))
    if is_manual_in_force(order):
        return f"{label} (zmieniono ręcznie w aplikacji)"
    return label


def order_requires_packing(order: OrderStatusFields) -> bool:
    """
    "Czeka na spakowanie / wymaga obsługi" z uwzględnieniem statusu
    aplikacyjnego. Z tej reguły liczą: licznik do spakowania, plakietka
    push, raport 9:00, czat po czyszczeniu 02:00 i flaga `requires_packing`
    w API.

    - ręcznie Nowe / W realizacji -> tak (jak NEW / PROCESSING z Allegro);
    - ręcznie Zrealizowane / Anulowane -> nie;
    - bez ręcznego statusu (albo już uzgodnionego z Allegro) - dotychczasowa
      reguła `requires_packing` z app/domain/fulfillment.py, bez zmian.
    """
    if is_manual_in_force(order):
        return order.app_status in OPEN_APP_STATUSES
    return requires_packing(order.status, order.fulfillment_status, order.tracking_number)


def order_needs_new_reminder(order: OrderStatusFields) -> bool:
    """
    Czy zamówienie trafia do przypomnienia o 20:00 (tylko "nietknięte").

    Ręcznie Nowe -> tak; ręcznie W realizacji -> nie (jest obsługiwane,
    bez powtarzających się alertów); zamknięte -> nie. Bez ręcznego
    statusu - jak dotąd: etap NEW i reguła `requires_packing`.
    """
    if is_manual_in_force(order):
        return order.app_status == APP_STATUS_NEW
    return (
        requires_packing(order.status, order.fulfillment_status, order.tracking_number)
        and (order.fulfillment_status or "").upper() == FULFILLMENT_NEW
    )


def order_awaits_shipment(order: OrderStatusFields) -> bool:
    """
    Kafel "Do wysyłki" i kandydaci check_waybills_job: dotychczasowa reguła
    `awaits_shipment`, ale bez zamówień ręcznie zamkniętych w aplikacji.
    """
    if is_closed_in_app(order):
        return False
    return awaits_shipment(order.status, order.fulfillment_status, order.tracking_number)
