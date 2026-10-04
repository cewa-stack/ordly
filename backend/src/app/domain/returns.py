"""
Statusy zwrotów klientów i JEDNA reguła "zwrot wymaga działania".

Wartości 1:1 z polem `status` schematu `CustomerReturn` w oficjalnym
swagger.yaml Allegro (`GET /order/customer-returns`, zasób beta):

    CREATED                 zwrot zgłoszony
    DISPATCHED              kupujący nadał paczkę
    IN_TRANSIT              paczka w drodze
    DELIVERED               paczka dostarczona - sprzedawca ma zwrócić pieniądze
    FINISHED                pieniądze zwrócone, zwrot zakończony
    FINISHED_APT            pieniądze zwrócone przez Allegro Protect, zakończony
    REJECTED                zwrot odrzucony
    COMMISSION_REFUND_CLAIMED  złożony wniosek o zwrot prowizji (po zwrocie pieniędzy)
    COMMISSION_REFUNDED     prowizja zwrócona (także automatycznie)
    WAREHOUSE_DELIVERED     paczka dotarła do magazynu Allegro (One Fulfillment)
    WAREHOUSE_VERIFICATION  magazyn Allegro weryfikuje zwrot

`CANCELLED` nie występuje w swaggerze, ale ORDLY od początku traktuje je
jako zamknięte (etykieta "Anulowany") - zostaje w zbiorze zamkniętych.

Z tej reguły liczą: licznik i plakietka "Zwroty" (AttentionService), pole
`requires_action` w `GET /returns` (desktop i telefon), bot (powiadomienie
o nowym zwrocie wychodzi tylko dla zwrotu wymagającego działania).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

RETURN_CREATED = "CREATED"
RETURN_DISPATCHED = "DISPATCHED"
RETURN_IN_TRANSIT = "IN_TRANSIT"
RETURN_DELIVERED = "DELIVERED"
RETURN_FINISHED = "FINISHED"
RETURN_FINISHED_APT = "FINISHED_APT"
RETURN_REJECTED = "REJECTED"
RETURN_COMMISSION_REFUND_CLAIMED = "COMMISSION_REFUND_CLAIMED"
RETURN_COMMISSION_REFUNDED = "COMMISSION_REFUNDED"
RETURN_WAREHOUSE_DELIVERED = "WAREHOUSE_DELIVERED"
RETURN_WAREHOUSE_VERIFICATION = "WAREHOUSE_VERIFICATION"
RETURN_CANCELLED = "CANCELLED"

#: Status wstawiany przez mapper przy niepełnej odpowiedzi - nigdy nie
#: nadpisuje statusu zapisanego w bazie.
UNKNOWN_RETURN_STATUS = "UNKNOWN"

#: Zwrot zakończony albo niewymagający już decyzji sprzedawcy.
#: - FINISHED / FINISHED_APT: pieniądze zwrócone, Allegro zamknęło sprawę;
#: - COMMISSION_REFUND_CLAIMED: pieniądze już zwrócone, wniosek o prowizję
#:   rozpatruje Allegro - sprzedawca nie ma tu nic do zrobienia;
#: - COMMISSION_REFUNDED: prowizja przyznana (ręcznie lub automatycznie);
#: - REJECTED, CANCELLED: sprawa zamknięta bez zwrotu.
CLOSED_RETURN_STATUSES = frozenset(
    {
        RETURN_FINISHED,
        RETURN_FINISHED_APT,
        RETURN_REJECTED,
        RETURN_COMMISSION_REFUND_CLAIMED,
        RETURN_COMMISSION_REFUNDED,
        RETURN_CANCELLED,
    }
)

_CANCELLED_ORDER_STATUS = "CANCELLED"

#: Nazwy dla użytkownika - te same w aplikacjach, bocie i push.
RETURN_STATUS_LABELS: dict[str, str] = {
    RETURN_CREATED: "Zgłoszony",
    RETURN_DISPATCHED: "Nadany przez kupującego",
    RETURN_IN_TRANSIT: "W drodze",
    RETURN_DELIVERED: "Dostarczony - zwróć pieniądze",
    RETURN_FINISHED: "Pieniądze zwrócone",
    RETURN_FINISHED_APT: "Zwrócone przez Allegro Protect",
    RETURN_REJECTED: "Odrzucony",
    RETURN_COMMISSION_REFUND_CLAIMED: "Prowizja do zwrotu",
    RETURN_COMMISSION_REFUNDED: "Prowizja zwrócona",
    RETURN_WAREHOUSE_DELIVERED: "W magazynie Allegro",
    RETURN_WAREHOUSE_VERIFICATION: "Weryfikacja w magazynie",
    RETURN_CANCELLED: "Anulowany",
}


#: Statusy, w których pieniądze zostały już oddane kupującemu (zwrot
#: pieniędzy) - z nich rejestr anulowań i zwrotów zapisuje "zwrot pieniędzy".
REFUNDED_RETURN_STATUSES = frozenset(
    {
        RETURN_FINISHED,
        RETURN_FINISHED_APT,
        RETURN_COMMISSION_REFUND_CLAIMED,
        RETURN_COMMISSION_REFUNDED,
    }
)


def is_refunded_return_status(status: str | None) -> bool:
    """Czy w tym statusie zwrotu pieniądze zostały już oddane."""
    return (status or "").upper() in REFUNDED_RETURN_STATUSES


def is_closed_return_status(status: str | None) -> bool:
    """Czy status zwrotu oznacza sprawę zakończoną."""
    return (status or "").upper() in CLOSED_RETURN_STATUSES


def return_requires_action(status: str | None, order_status: str | None = None) -> bool:
    """
    Czy zwrot wymaga działania sprzedawcy.

    Nie wymaga, gdy status jest zamknięty (patrz CLOSED_RETURN_STATUSES)
    albo gdy zamówienie, którego dotyczy, zostało anulowane - wtedy nie ma
    już czego zwracać ani o czym decydować. Każdy inny status (także
    nieznany) jest pokazywany jako wymagający uwagi: lepiej raz za dużo
    niż przeoczyć zwrot.
    """
    if is_closed_return_status(status):
        return False
    return (order_status or "").upper() != _CANCELLED_ORDER_STATUS


#: Skąd przyszła zmiana statusu zwrotu - trafia do historii (audytu).
RETURN_CHANGE_SOURCE_ALLEGRO = "allegro"


@dataclass(frozen=True, slots=True)
class ReturnStatusChange:
    """Jedna zmiana statusu zwrotu - wpis historii: kiedy, skąd, z czego na co."""

    external_id: str
    marketplace: str
    order_external_id: str
    previous_status: str
    new_status: str
    source: str
    changed_at: datetime

    @property
    def closes_return(self) -> bool:
        """Czy ta zmiana zakończyła sprawę (otwarty -> zamknięty)."""
        return not is_closed_return_status(self.previous_status) and is_closed_return_status(
            self.new_status
        )


def is_reopening(previous_status: str, new_status: str) -> bool:
    """
    Czy zmiana cofałaby zakończony zwrot do otwartego statusu.

    Oś statusów zwrotu na Allegro idzie tylko do przodu (zgłoszony ->
    w drodze -> dostarczony -> zakończony). Otwarty status po zamkniętym
    to nieaktualna odpowiedź, a nie nowy fakt - nie wolno nią przywrócić
    zwrotu do obsługi. Zmiany między zamkniętymi (np. FINISHED ->
    COMMISSION_REFUND_CLAIMED -> COMMISSION_REFUNDED) są dozwolone.
    """
    return is_closed_return_status(previous_status) and not is_closed_return_status(new_status)


def return_status_label(status: str) -> str:
    """Nazwa statusu dla człowieka; nieznany status zostaje surowy."""
    return RETURN_STATUS_LABELS.get((status or "").upper(), status)
