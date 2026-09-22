"""
"Wymaga uwagi" - te same trzy liczby, które pokazuje ekran Start.

Do spakowania · Dyskusje · Zwroty. Z nich powstaje plakietka na ikonie
aplikacji (przy KAŻDYM powiadomieniu push) i poranny raport o 9:00.

Zasada: liczby mają być IDENTYCZNE z tym, co widać po otwarciu aplikacji.
Dlatego serwis liczy dokładnie z tych samych list i tą samą regułą co
aplikacje:

- zamówienia: 100 ostatnich (tyle pobiera `GET /orders?limit=100`
  i desktop, i telefon), reguła 1:1 z `isPendingOrder` na desktopie
  i `isPendingFulfillment` na telefonie;
- zwroty: 50 ostatnich (domyślny limit `GET /returns`), bez zamkniętych;
- dyskusje: z API Allegro (nie ma ich w bazie), tylko z aktywnym czatem.

Dotąd każde powiadomienie ustawiało plakietkę po swojemu: nowe zamówienie
jej nie ruszało, dyskusja wbijała na sztywno 1, przypomnienie liczyło same
paczki - liczba na ikonie nie zgadzała się z niczym w aplikacji.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from app.domain.entities.order import Order
from app.domain.interfaces.order_repository import OrderRepository
from app.domain.interfaces.return_repository import ReturnRepository
from app.services.issues_service import IssuesService

#: Tyle zamówień pobierają aplikacje (`GET /orders?limit=100`).
ORDERS_WINDOW = 100
#: Domyślny limit `GET /returns` - tyle zwrotów widzą aplikacje.
RETURNS_WINDOW = 50

#: Zwroty, które nie wymagają już niczego od sprzedawcy - te same, które
#: aplikacje pokazują wygaszone (desktop ShellLayout, mobile StartScreen).
CLOSED_RETURN_STATUSES = frozenset({"COMMISSION_REFUNDED", "CANCELLED", "REJECTED"})

_SHIPPED = frozenset({"SENT", "PICKED_UP"})
_WAITING_FOR_PACKING = frozenset({"NEW", "PROCESSING"})


def is_pending_packing(order: Order) -> bool:
    """
    Zamówienie czeka na spakowanie - 1:1 z `isPendingOrder` (desktop).

    Anulowane odpada, nawet gdy Allegro zostawiło mu etap NEW. Wysłane
    odpada też wtedy, gdy ORDLY samo wykryło numer przesyłki, zanim status
    zmienił się na Allegro. Spakowane (READY_FOR_SHIPMENT) czeka już tylko
    na kuriera, więc do "do spakowania" się nie liczy.
    """
    status = (order.status or "").upper()
    fulfillment = (order.fulfillment_status or "").upper() or None
    if status == "CANCELLED" or fulfillment == "CANCELLED":
        return False
    if (fulfillment in _SHIPPED) or order.tracking_number:
        return False
    return fulfillment is None or fulfillment in _WAITING_FOR_PACKING


@dataclass(frozen=True, slots=True)
class AttentionCounts:
    """Trzy liczby z ekranu Start plus najstarsze czekające zamówienie."""

    pending: int
    #: `None` = Allegro nie odpowiedziało i nie wiemy, ile jest dyskusji.
    open_issues: int | None
    open_returns: int
    #: Data (UTC, jak w bazie) najstarszego zamówienia do spakowania.
    oldest_pending_utc: datetime | None

    @property
    def badge(self) -> int | None:
        """
        Liczba na ikonie. `None`, gdy nie znamy liczby dyskusji - lepiej
        zostawić plakietkę bez zmian niż pokazać zaniżoną liczbę.
        """
        if self.open_issues is None:
            return None
        return self.pending + self.open_issues + self.open_returns


class AttentionService:
    """Liczy "Wymaga uwagi" tak samo, jak robią to aplikacje."""

    def __init__(
        self,
        order_repository: OrderRepository,
        return_repository: ReturnRepository,
        issues_service: IssuesService,
    ) -> None:
        self._orders = order_repository
        self._returns = return_repository
        self._issues = issues_service

    async def counts(self) -> AttentionCounts:
        orders = await self._orders.get_recent(limit=ORDERS_WINDOW)
        pending = [order for order in orders if is_pending_packing(order)]

        returns = await self._returns.get_recent(limit=RETURNS_WINDOW)
        open_returns = sum(1 for item in returns if item.status not in CLOSED_RETURN_STATUSES)

        # Dyskusje żyją tylko w API Allegro. Awaria nie może zablokować
        # powiadomienia - brak liczby oznacza "plakietka bez zmian".
        try:
            issues = await self._issues.list_issues()
            open_issues: int | None = sum(1 for issue in issues if issue.chat_active)
        except Exception as exc:  # noqa: BLE001 - powiadomienie ma wyjść mimo to
            logger.warning("Plakietka push: nie udało się pobrać dyskusji ({})", exc)
            open_issues = None

        return AttentionCounts(
            pending=len(pending),
            open_issues=open_issues,
            open_returns=open_returns,
            oldest_pending_utc=min((o.order_date for o in pending), default=None),
        )
