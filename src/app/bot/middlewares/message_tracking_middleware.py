"""
Middleware klienta aiogram rejestrujące identyfikatory wysłanych wiadomości.

Działa na poziomie sesji bota (a nie pojedynczego handlera), dzięki czemu
przechwytuje KAŻDĄ wiadomość wysłaną przez bota - zarówno powiadomienia
biznesowe, jak i odpowiedzi na komendy. Zapisane identyfikatory są potem
wykorzystywane przez nocne czyszczenie czatu (02:00) do usunięcia wszystkich
wcześniejszych wiadomości bota.

WAŻNE: `make_request` zwraca gotowy obiekt encji (np. `Message`)
BEZPOŚREDNIO, a nie opakowany w `Response` - mimo że sygnatura
`BaseRequestMiddleware.__call__` w aiogram deklaruje typ zwracany jako
`Response[TelegramType]`. To rozbieżność między adnotacją typu a
rzeczywistym zachowaniem biblioteki w wersji 3.30 - nie polegać na `.result`.

Cała logika śledzenia (łącznie z samym odczytem odpowiedzi) jest objęta
try/except na najwyższym poziomie - błąd w śledzeniu NIE MOŻE przerwać
wysyłki wiadomości do użytkownika, niezależnie od tego, na jakim etapie
by się pojawił.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiogram import Bot
from aiogram.client.session.middlewares.base import (
    BaseRequestMiddleware,
    NextRequestMiddlewareType,
)
from aiogram.methods import SendMessage
from aiogram.methods.base import TelegramMethod, TelegramType
from aiogram.types import Message
from loguru import logger

from app.bot.middlewares.session_context import get_current_session

if TYPE_CHECKING:
    from app.container import Container


class MessageTrackingMiddleware(BaseRequestMiddleware):
    """Zapisuje ID wiadomości wysłanych przez bota na czat administratora."""

    def __init__(self, container: Container, admin_chat_id: int) -> None:
        """
        Args:
            container: Kontener DI (dostęp do sesji i repozytorium wiadomości).
            admin_chat_id: Chat, którego wiadomości mają być śledzone.
        """
        self._container = container
        self._admin_chat_id = admin_chat_id

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> TelegramType:
        """
        Wykonuje żądanie i - dla wysyłki wiadomości - rejestruje jej ID.

        Śledzenie jest całkowicie odseparowane od samej wysyłki: `result`
        (odpowiedź Telegrama) jest zwracane wywołującemu niezależnie od
        tego, czy próba śledzenia się powiodła.

        Adnotacja zwracanego typu (`TelegramType`) celowo odbiega od
        deklaracji w `BaseRequestMiddleware.__call__` (`Response[TelegramType]`)
        - ta ostatnia jest błędna względem rzeczywistego zachowania
        `AiohttpSession.make_request()`, które zwraca encję bezpośrednio
        (potwierdzone testem end-to-end na realnym obiekcie Bot).
        """
        result = await make_request(bot, method)

        if isinstance(method, SendMessage):
            try:
                await self._track(result)
            except Exception:
                # Śledzenie jest pomocnicze - jego błąd (na dowolnym etapie)
                # nie może wpłynąć na już dostarczoną wiadomość.
                logger.exception(
                    "Nie udało się zarejestrować wysłanej wiadomości do "
                    "czyszczenia czatu (śledzenie pominięte, wiadomość dostarczona)"
                )

        return result  # type: ignore[return-value]

    async def _track(self, result: Any) -> None:
        """Zapisuje ID wiadomości do bazy, ignorując wiadomości spoza czatu admina."""
        if not isinstance(result, Message):
            return
        if result.chat.id != self._admin_chat_id:
            return

        session = get_current_session()
        if session is not None:
            # Wysyłka w ramach handlera - zapis w jego sesji (to samo
            # połączenie), by uniknąć rywalizacji o blokadę zapisu SQLite.
            await self._container.telegram_message_repository(session).record(
                chat_id=result.chat.id, message_id=result.message_id
            )
        else:
            # Wysyłka poza handlerem (powiadomienie, zadanie schedulera) -
            # brak otwartej sesji, więc otwieramy własną.
            async with self._container.session_scope() as own_session:
                await self._container.telegram_message_repository(own_session).record(
                    chat_id=result.chat.id, message_id=result.message_id
                )
