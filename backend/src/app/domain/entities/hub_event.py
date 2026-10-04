"""
Zdarzenie dla ORDLy Control Hub - fizycznej konsoli powiadomień na ESP32.

Hub niczego nie liczy: dostaje gotowe zdarzenia przez MQTT, pokazuje je,
zapala diody i odsyła potwierdzenie przyciskiem OK. Stan "co jeszcze
czeka" trzyma ORDLY (tabela `hub_events`), bo Hub po restarcie albo
zerwaniu Wi-Fi nic nie pamięta - dostaje wtedy od ORDLY komplet
aktywnych zdarzeń jeszcze raz (temat `ordly/events/snapshot`).

Kolory (`priority`) i znaczenie diod: sekcje 7-9 specyfikacji Control Huba.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

#: Czerwona dioda - zamówienia.
PRIORITY_RED = "red"
#: Pomarańczowa dioda - zwroty, dyskusje, wiadomości od klientów.
PRIORITY_AMBER = "amber"
#: Niebieska dioda miga szybko - problem z systemem.
PRIORITY_BLUE = "blue"

TYPE_NEW_ORDER = "new_order"
TYPE_RETURN = "return_requested"
TYPE_DISPUTE = "dispute"
TYPE_MESSAGE = "message"
TYPE_SYSTEM_PROBLEM = "system_problem"

#: Zamknięte przyciskiem OK na Hubie.
REASON_ACKNOWLEDGED = "acknowledged"
#: Zamknięte, bo sprawa zmieniła się w ORDLY (pakowanie, anulowanie, zamknięty zwrot).
REASON_STATUS_CHANGED = "status_changed"
#: Problem z systemem minął sam (kanał znowu odpowiada).
REASON_RECOVERED = "recovered"


@dataclass(frozen=True, slots=True)
class HubEvent:
    """
    Jedno zdarzenie widoczne na Hubie, dopóki ktoś go nie potwierdzi
    albo sprawa nie rozwiąże się w ORDLY.

    `source_key` wiąże zdarzenie z jego źródłem (np. `order:allegro:123`)
    i jest unikalny - ponowne wykrycie tego samego zamówienia nie tworzy
    drugiego wpisu na Hubie, a zmiana statusu zamówienia wie, które
    zdarzenie zamknąć.
    """

    id: int
    source_key: str
    type: str
    priority: str
    created_at: datetime
    data: dict[str, Any] = field(default_factory=dict)
    acked_at: datetime | None = None
    resolved_at: datetime | None = None
    resolve_reason: str | None = None

    @property
    def event_id(self) -> str:
        """Identyfikator w protokole MQTT (pole `id` / `event_id`)."""
        return f"evt_{self.id}"

    @property
    def is_active(self) -> bool:
        """Czy zdarzenie wciąż czeka na Hubie."""
        return self.acked_at is None and self.resolved_at is None


def parse_event_id(value: object) -> int | None:
    """
    Zamienia `evt_123` z wiadomości Huba na numer wiersza w bazie.

    Wiadomość przychodzi z sieci - wszystko, co nie ma dokładnie tej
    postaci, jest ignorowane zamiast wywracać obsługę potwierdzeń.
    """
    if not isinstance(value, str) or not value.startswith("evt_"):
        return None
    number = value[4:]
    if not number.isdigit():
        return None
    return int(number)
