"""Serwis dyskusji/reklamacji marketplace - wyłącznie na żywo, bez cache'owania."""

from __future__ import annotations

from loguru import logger

from app.domain.entities.issue import Issue, IssueMessage
from app.domain.exceptions.domain_exceptions import MarketplaceUnavailableError
from app.domain.interfaces.marketplace_plugin import MarketplacePlugin
from app.infrastructure.plugins.allegro.exceptions import AllegroApiError


class IssuesService:
    """
    Pobiera dyskusje/reklamacje i wysyła odpowiedzi bezpośrednio na
    marketplace - tak jak TrackingService, nic tutaj nie jest
    cache'owane do wyświetlania. Dyskusje są rzadkie, więc świeżość
    danych jest ważniejsza niż koszt dodatkowego zapytania.
    """

    def __init__(self, plugin: MarketplacePlugin) -> None:
        self._plugin = plugin

    async def list_issues(self) -> list[Issue]:
        """Zwraca aktualną listę dyskusji i reklamacji z marketplace."""
        try:
            return await self._plugin.get_issues()
        except AllegroApiError as exc:
            logger.warning("Marketplace niedostępne przy pobieraniu dyskusji: {}", exc)
            raise MarketplaceUnavailableError(str(exc)) from exc

    async def get_thread(self, issue_id: str) -> list[IssueMessage]:
        """
        Zwraca wątek wiadomości dyskusji/reklamacji w kolejności
        chronologicznej - najstarsza pierwsza, najnowsza ostatnia.

        Allegro zwraca `/sale/issues/{id}/chat` od najnowszej wiadomości
        (typowe dla paginowanych API), czyli odwrotnie niż czyta się
        rozmowę w komunikatorze. Sortowanie siedzi TUTAJ, a nie w każdym
        kliencie z osobna: desktop i mobile dostają jedną, gotową
        kolejność, więc kolejny ekran nie odziedziczy tego błędu przez
        zapomniane `sort()`.

        Wiadomości z identycznym `created_at` zachowują kolejność
        z marketplace - stabilne `sorted()` nie ma czym ich rozstrzygnąć,
        a zgadywanie byłoby gorsze niż zostawienie decyzji Allegro.
        """
        try:
            messages = await self._plugin.get_issue_messages(issue_id)
        except AllegroApiError as exc:
            logger.warning(
                "Marketplace niedostępne przy pobieraniu wątku {}: {}", issue_id, exc
            )
            raise MarketplaceUnavailableError(str(exc)) from exc
        return sorted(messages, key=lambda message: message.created_at)

    async def reply(self, issue_id: str, text: str) -> None:
        """Wysyła odpowiedź sprzedawcy w danej dyskusji/reklamacji."""
        try:
            await self._plugin.reply_to_issue(issue_id, text)
        except AllegroApiError as exc:
            logger.warning(
                "Marketplace niedostępne przy wysyłaniu odpowiedzi do {}: {}",
                issue_id,
                exc,
            )
            raise MarketplaceUnavailableError(str(exc)) from exc
