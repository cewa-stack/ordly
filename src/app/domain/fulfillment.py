"""
Statusy realizacji zamówienia (fulfillment) i pomocnicze predykaty domenowe.

`fulfillment_status` odzwierciedla etap fizycznej obsługi zamówienia
(nowe -> pakowane -> wysłane) i jest niezależny od statusu płatności
checkout-formu. To właśnie ten status zmienia się, gdy sprzedawca pakuje
i nadaje paczkę - dlatego opierają się na nim: przypomnienie o niewysłanych
zamówieniach (20:00), nocne czyszczenie czatu (02:00) oraz SMS wysyłany
w momencie rozpoczęcia pakowania.

Nazwy statusów odpowiadają wartościom zwracanym przez Allegro w polu
`fulfillment.status` checkout-formu. Trzymamy je w jednym miejscu, aby
żaden moduł domenowy nie odwoływał się do surowych literałów.
"""

from __future__ import annotations

FULFILLMENT_NEW = "NEW"
FULFILLMENT_PROCESSING = "PROCESSING"
FULFILLMENT_READY_FOR_SHIPMENT = "READY_FOR_SHIPMENT"
FULFILLMENT_READY_FOR_PICKUP = "READY_FOR_PICKUP"
FULFILLMENT_SENT = "SENT"
FULFILLMENT_PICKED_UP = "PICKED_UP"
FULFILLMENT_SUSPENDED = "SUSPENDED"

# Statusy oznaczające, że zamówienie zostało już wysłane / odebrane -
# takie zamówienie nie wymaga już pakowania ani nadania.
SHIPPED_FULFILLMENT_STATUSES = frozenset({FULFILLMENT_SENT, FULFILLMENT_PICKED_UP})

# Statusy, w których zamówienie jest wciąż "w toku" i powinno pozostać
# widoczne na czacie po nocnym czyszczeniu (nowe lub w trakcie pakowania).
ACTIVE_FULFILLMENT_STATUSES = frozenset({FULFILLMENT_NEW, FULFILLMENT_PROCESSING})

# Status wyzwalający SMS "rozpoczęto pakowanie".
PACKING_STARTED_FULFILLMENT_STATUS = FULFILLMENT_PROCESSING


def is_shipped(fulfillment_status: str | None) -> bool:
    """Czy dany status realizacji oznacza, że zamówienie zostało wysłane."""
    if fulfillment_status is None:
        return False
    return fulfillment_status.upper() in SHIPPED_FULFILLMENT_STATUSES


def is_packing_started(previous_status: str | None, current_status: str | None) -> bool:
    """
    Czy nastąpiło przejście na etap pakowania (PROCESSING).

    Zwraca True tylko dla właściwej zmiany etapu - nie dla powtórnego
    ustawienia tego samego statusu, dzięki czemu SMS o pakowaniu
    wychodzi dokładnie raz.
    """
    if current_status is None:
        return False
    normalized_current = current_status.upper()
    normalized_previous = previous_status.upper() if previous_status else None
    return (
        normalized_current == PACKING_STARTED_FULFILLMENT_STATUS
        and normalized_previous != PACKING_STARTED_FULFILLMENT_STATUS
    )
