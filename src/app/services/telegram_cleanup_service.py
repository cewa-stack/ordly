"""
Serwis nocnego czyszczenia czatu Telegram (job 02:00).

Usuwa wszystkie wcześniejsze wiadomości wysłane przez bota TOOM, a
następnie publikuje ponownie wyłącznie aktualne (nowe/pakowane)
zamówienia. Dzięki temu rano na czacie widoczne są tylko zamówienia
wymagające obsługi, bez starych, nieaktualnych wiadomości.

Operacja jest celowo podzielona na dwie fazy uruchamiane w osobnych
transakcjach (zob. run_telegram_cleanup_job):

1. purge_previous_messages() - usuwa wiadomości i czyści rejestr (ZAPIS
   do tabeli telegram_messages).
2. repost_active_orders() - publikuje aktualne zamówienia; nowa wiadomość
   jest rejestrowana przez middleware sesji bota w JESZCZE innej transakcji.

Rozdzielenie faz zapobiega zakleszczeniu SQLite: gdyby ponowna publikacja
odbywała się w tej samej otwartej transakcji, która trzyma blokadę zapisu
po wyczyszczeniu rejestru, zapis middleware czekałby na jej zwolnienie
w nieskończoność.
"""

from __future__ import annotations

from aiogram import Bot
from loguru import logger

from app.domain.interfaces.notifier import Notifier
from app.domain.interfaces.order_repository import OrderRepository
from app.domain.interfaces.telegram_message_repository import (
    TelegramMessageRepository,
)

# Ile aktywnych zamówień publikować ponownie po czyszczeniu. Odpowiada oknu
# synchronizacji Allegro - realnie aktywnych zamówień jest znacznie mniej.
_ACTIVE_ORDERS_LIMIT = 50


class TelegramCleanupService:
    """Czyści czat i ponownie publikuje aktualne zamówienia."""

    def __init__(
        self,
        bot: Bot,
        admin_chat_id: int,
        order_repository: OrderRepository,
        message_repository: TelegramMessageRepository,
        notifier: Notifier,
    ) -> None:
        """
        Args:
            bot: Instancja bota (do usuwania wiadomości po ID).
            admin_chat_id: Chat, na którym pracuje bot.
            order_repository: Dostęp do zamówień (lista aktywnych).
            message_repository: Rejestr wysłanych wiadomości bota.
            notifier: Kanał publikacji ponownej listy zamówień.
        """
        self._bot = bot
        self._admin_chat_id = admin_chat_id
        self._order_repository = order_repository
        self._message_repository = message_repository
        self._notifier = notifier

    async def purge_previous_messages(self) -> int:
        """
        Usuwa wszystkie zarejestrowane wiadomości bota i czyści rejestr.

        Usuwanie jest odporne na błędy pojedynczej wiadomości (np. zbyt
        stara, by Telegram pozwolił ją usunąć, lub już usunięta ręcznie) -
        taka wiadomość jest pomijana, a proces kontynuowany.

        Returns:
            Liczba faktycznie usuniętych wiadomości.
        """
        tracked = await self._message_repository.get_all()
        deleted = 0
        for message in tracked:
            try:
                await self._bot.delete_message(
                    chat_id=message.chat_id, message_id=message.message_id
                )
                deleted += 1
            except Exception as exc:
                # Wiadomość zbyt stara (>48h), już usunięta lub niedostępna -
                # to normalny przypadek, nie błąd krytyczny.
                logger.debug(
                    "Nie udało się usunąć wiadomości {}/{}: {}",
                    message.chat_id,
                    message.message_id,
                    exc,
                )

        removed = await self._message_repository.delete_all()
        logger.info(
            "Nocne czyszczenie czatu: usunięto {} wiadomości (rejestr: {})",
            deleted,
            removed,
        )
        return deleted

    async def repost_active_orders(self) -> int:
        """
        Publikuje ponownie aktualne (nowe/pakowane) zamówienia.

        Gdy nie ma aktywnych zamówień, nie wysyła nic - czat pozostaje
        pusty, zgodnie z zasadą "tylko aktualne zamówienia".

        Returns:
            Liczba opublikowanych zamówień.
        """
        active_orders = await self._order_repository.get_active(_ACTIVE_ORDERS_LIMIT)
        if active_orders:
            await self._notifier.notify_active_orders(active_orders)
            logger.info(
                "Nocne czyszczenie czatu: opublikowano {} aktualnych zamówień",
                len(active_orders),
            )
        else:
            logger.info("Nocne czyszczenie czatu: brak aktywnych zamówień do publikacji")
        return len(active_orders)
