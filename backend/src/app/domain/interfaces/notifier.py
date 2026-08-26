"""Abstrakcja wysyłki powiadomień, niezależna od Telegrama."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.allegro_lokalnie_event import AllegroLokalnieEvent
from app.domain.entities.dispute_notice import DisputeNotice
from app.domain.entities.order import Order
from app.domain.entities.order_return import OrderReturn
from app.shared.dto.reminder_dto import ShippingReminderData


class Notifier(ABC):
    """
    Kontrakt wysyłki powiadomień o zdarzeniach biznesowych.

    Dzisiaj jedyną implementacją jest Telegram (bot ORDLY), ale
    interfejs pozwala w przyszłości dodać np. e-mail lub push bez
    zmiany logiki w services/.
    """

    @abstractmethod
    async def notify_new_order(self, order: Order) -> None:
        """Wysyła powiadomienie o nowym zamówieniu."""
        raise NotImplementedError

    @abstractmethod
    async def notify_order_cancelled(self, order: Order) -> None:
        """Wysyła powiadomienie o anulowaniu zamówienia."""
        raise NotImplementedError

    @abstractmethod
    async def notify_order_return(self, order_return: OrderReturn) -> None:
        """Wysyła powiadomienie o zwrocie produktów z zamówienia."""
        raise NotImplementedError

    @abstractmethod
    async def notify_low_stock(self, name: str, sku: str, stock: int, min_stock: int) -> None:
        """Wysyła ostrzeżenie o osiągnięciu minimalnego stanu magazynowego."""
        raise NotImplementedError

    @abstractmethod
    async def notify_shipping_reminder(self, data: ShippingReminderData) -> None:
        """Wysyła przypomnienie o zamówieniach wymagających dziś wysyłki (20:00)."""
        raise NotImplementedError

    @abstractmethod
    async def notify_active_orders(self, orders: list[Order]) -> None:
        """
        Publikuje listę aktualnych (nowych/pakowanych) zamówień po nocnym
        czyszczeniu czatu (02:00).
        """
        raise NotImplementedError

    @abstractmethod
    async def send_text(self, text: str) -> None:
        """Wysyła dowolną wiadomość tekstową (np. alert o błędzie)."""
        raise NotImplementedError

    async def notify_allegro_lokalnie(self, event: AllegroLokalnieEvent) -> None:
        """
        Zgłasza zdarzenie z Allegro Lokalnie (nowe zamówienie, wiadomość,
        zmiana statusu) odczytane z powiadomienia e-mail.

        Ma domyślną implementację opartą o `send_text` - tak jak
        `notify_sync_failed` - żeby dodanie nowego kanału powiadomień nie
        wymagało od razu własnego formatowania. Oba istniejące kanały tę
        metodę nadpisują: Telegram własnym układem HTML, Web Push
        pozycją z katalogu `push_payload`.
        """
        await self.send_text(f"Allegro Lokalnie: {event.subject or event.snippet}")

    async def notify_new_dispute(self, notice: DisputeNotice) -> None:
        """
        Zgłasza, że kupujący rozpoczął dyskusję.

        Ma domyślną implementację opartą o `send_text`, żeby nowy kanał
        powiadomień nie musiał od razu mieć własnego formatowania. Oba
        istniejące kanały ją nadpisują.
        """
        await self.send_text(
            f"Nowa dyskusja: {notice.buyer_login}"
            + (f" - {notice.reason}" if notice.reason else "")
        )

    async def notify_unmatched_products(
        self, reference: str, product_names: list[str]
    ) -> None:
        """
        Ostrzega, że sprzedane pozycje nie mają powiązania z magazynem,
        więc stany się nie zmieniły.

        Ma domyślną implementację opartą o `send_text` - jak
        `notify_sync_failed` - żeby nowy kanał powiadomień nie musiał od
        razu mieć własnego formatowania. Oba istniejące kanały ją
        nadpisują: Telegram bogatym układem HTML z komendą do skopiowania,
        Web Push pozycją z katalogu `push_payload`.
        """
        await self.send_text(
            f"Sprzedaż poza magazynem: zamówienie {reference} zawiera pozycje bez "
            f"powiązania z magazynem ({', '.join(product_names)}) - stan bez zmian."
        )

    async def notify_sync_failed(self, channel: str, retry_in_minutes: int) -> None:
        """
        Alarmuje, że kanał sprzedaży nie odpowiada.

        Ma domyślną implementację opartą o `send_text`, bo nie każdy
        kanał powiadomień potrzebuje osobnego formatowania - liczy się,
        żeby informacja w ogóle dotarła. Web Push nadpisuje tę metodę
        własnym układem z katalogu powiadomień.

        Wywoływane dopiero po DRUGIEJ nieudanej próbie z rzędu
        (`SyncFailureTracker`), nigdy przy pojedynczym timeoucie.
        """
        await self.send_text(
            f"{channel.capitalize()} nie odpowiedziało. "
            f"Ordi spróbuje ponownie za {retry_in_minutes} min."
        )
