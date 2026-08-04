"""Abstrakcja wysyłki powiadomień, niezależna od Telegrama."""

from __future__ import annotations

from abc import ABC, abstractmethod

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
