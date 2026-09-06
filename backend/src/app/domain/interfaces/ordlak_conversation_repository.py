"""Abstrakcyjny kontrakt dostępu do zapisanych rozmów z asystentem."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.ordlak_conversation import (
    ChatRole,
    OrdlakConversation,
    OrdlakMessage,
)


class OrdlakConversationRepository(ABC):
    """Kontrakt przechowywania wątków rozmowy, niezależny od bazy danych."""

    @abstractmethod
    async def create(self, title: str) -> OrdlakConversation:
        """Zakłada nowy wątek i zwraca go z nadanym `id`."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, conversation_id: int) -> OrdlakConversation | None:
        """
        Zwraca wątek razem z wiadomościami (najstarsza pierwsza).

        `None` = wątku nie ma. Rozróżnienie ma znaczenie: aplikacja
        pokazuje wtedy "ta rozmowa została usunięta" zamiast pustego
        okna, które wyglądałoby jak zepsuty czat.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_recent(self, limit: int = 30) -> list[OrdlakConversation]:
        """Zwraca wątki bez wiadomości, od ostatnio używanego."""
        raise NotImplementedError

    @abstractmethod
    async def append(
        self,
        conversation_id: int,
        role: ChatRole,
        content: str,
        used_tools: tuple[str, ...] = (),
    ) -> OrdlakMessage:
        """
        Dopisuje wypowiedź do wątku i odświeża jego `updated_at`.

        Odświeżenie jest częścią zapisu, a nie osobnym krokiem - lista
        rozmów sortuje się po tej kolumnie, więc wątek, do którego właśnie
        coś dopisano, musi wskoczyć na górę.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, conversation_id: int) -> bool:
        """Usuwa wątek z wiadomościami. `False` = nie było czego usuwać."""
        raise NotImplementedError
