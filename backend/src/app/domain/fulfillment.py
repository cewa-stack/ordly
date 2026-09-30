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
FULFILLMENT_CANCELLED = "CANCELLED"
FULFILLMENT_RETURNED = "RETURNED"

# Status płatności wstawiany przez mapper, gdy odpowiedź marketplace nie
# zawiera pola `status` (niepełna odpowiedź). Nigdy nie nadpisuje
# statusu zapisanego w bazie.
UNKNOWN_ORDER_STATUS = "UNKNOWN"

# `fulfillment.shipmentSummary.lineItemsSent` - ile pozycji zamówienia ma
# już numer przesyłki. SOME/ALL = Allegro zna numer, nawet jeśli etap
# realizacji nadal jest NEW/PROCESSING (sprzedawca nie ma włączonej
# automatycznej zmiany statusu po dodaniu numeru).
LINE_ITEMS_SENT_WITH_WAYBILL = frozenset({"SOME", "ALL"})

# Statusy oznaczające, że zamówienie zostało już wysłane / odebrane -
# takie zamówienie nie wymaga już pakowania ani nadania.
SHIPPED_FULFILLMENT_STATUSES = frozenset({FULFILLMENT_SENT, FULFILLMENT_PICKED_UP})

# Statusy, w których zamówienie jest wciąż "w toku" i powinno pozostać
# widoczne na czacie po nocnym czyszczeniu (nowe lub w trakcie pakowania).
# To jednocześnie etapy "do spakowania" - patrz requires_packing().
ACTIVE_FULFILLMENT_STATUSES = frozenset({FULFILLMENT_NEW, FULFILLMENT_PROCESSING})
PACKING_FULFILLMENT_STATUSES = ACTIVE_FULFILLMENT_STATUSES

# Etapy "czeka na nadanie": do spakowania plus spakowane, czekające na
# kuriera. Każdy inny etap (wysłane, odebrane, do odbioru osobistego,
# wstrzymane, anulowane, zwrócone) nie jest "do wysyłki".
AWAITING_SHIPMENT_FULFILLMENT_STATUSES = frozenset(
    {FULFILLMENT_NEW, FULFILLMENT_PROCESSING, FULFILLMENT_READY_FOR_SHIPMENT}
)

# Statusy, w których zamówienie wciąż może się zmienić na Allegro i których
# nie wolno zostawić "zamrożonych" w bazie, gdy zamówienie wypadnie poza
# okno synchronizacji (50 najnowszych checkout-formów). Zamówienie
# w jednym z nich - albo z nieznanym etapem (NULL) - jest odświeżane
# pojedynczo w każdym cyklu, dopóki Allegro nie poda etapu końcowego
# (SENT, PICKED_UP, CANCELLED, RETURNED...).
REFRESHABLE_FULFILLMENT_STATUSES = AWAITING_SHIPMENT_FULFILLMENT_STATUSES

# Status wyzwalający SMS "rozpoczęto pakowanie".
PACKING_STARTED_FULFILLMENT_STATUS = FULFILLMENT_PROCESSING


def _normalized(value: str | None) -> str | None:
    return value.upper() if value else None


def is_cancelled_order(status: str | None, fulfillment_status: str | None) -> bool:
    """Anulowane - po statusie płatności ALBO po etapie realizacji."""
    return (
        _normalized(status) == FULFILLMENT_CANCELLED
        or _normalized(fulfillment_status) == FULFILLMENT_CANCELLED
    )


def requires_packing(
    status: str | None, fulfillment_status: str | None, tracking_number: str | None
) -> bool:
    """
    JEDNA reguła "zamówienie czeka na spakowanie" dla całego ORDLY.

    Z niej liczą: licznik "X zamówień czeka na spakowanie", plakietka
    push, poranny raport 9:00, lista "Do spakowania" (desktop i telefon
    dostają gotową flagę `requires_packing` z API) oraz bot (czat po
    czyszczeniu 02:00; przypomnienie 20:00 to jej podzbiór - tylko NEW).
    Zapytania SQL w SqliteOrderRepository są jej lustrem i test pilnuje,
    żeby się nie rozjechały.

    Czeka na spakowanie = nieanulowane, bez numeru przesyłki i z etapem
    NEW albo PROCESSING. Numer przesyłki wygrywa z etapem: Allegro potrafi
    zostawić NEW po nadaniu, gdy sprzedawca nie ma automatycznej zmiany
    statusu.

    Etap nieznany (NULL) NIE czeka na spakowanie. NULL mają rekordy,
    których Allegro nigdy nie potwierdziło (sprzed śledzenia etapów);
    synchronizacja dopytuje o nie w każdym cyklu i uzupełnia etap, a do
    tego czasu nie mogą nabijać licznika - dokładnie tak powstało
    przypomnienie o zamówieniu sprzed 170 dni.
    """
    if is_cancelled_order(status, fulfillment_status) or tracking_number:
        return False
    return _normalized(fulfillment_status) in PACKING_FULFILLMENT_STATUSES


def awaits_shipment(
    status: str | None, fulfillment_status: str | None, tracking_number: str | None
) -> bool:
    """
    Zamówienie czeka na nadanie (kafel "Do wysyłki", kandydaci
    check_waybills_job): jak requires_packing(), plus spakowane
    (READY_FOR_SHIPMENT), które czekają już tylko na kuriera.
    """
    if is_cancelled_order(status, fulfillment_status) or tracking_number:
        return False
    return _normalized(fulfillment_status) in AWAITING_SHIPMENT_FULFILLMENT_STATUSES


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
