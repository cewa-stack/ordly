"""Kontrakt dostępu do szablonów odpowiedzi w dyskusjach."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.reply_template import ReplyTemplate


class ReplyTemplateRepository(ABC):
    """Przechowuje szablony odpowiedzi, wspólne dla desktopu i telefonu."""

    @abstractmethod
    async def list_all(self) -> list[ReplyTemplate]:
        """Zwraca wszystkie szablony w kolejności wyświetlania."""
        raise NotImplementedError

    @abstractmethod
    async def add(self, title: str, body: str) -> ReplyTemplate:
        """Dodaje szablon na końcu listy i zwraca go z nadanym `id`."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, template_id: int, title: str, body: str) -> ReplyTemplate | None:
        """Zmienia tytuł i treść. `None`, gdy szablonu o tym `id` nie ma."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, template_id: int) -> bool:
        """Usuwa szablon. `False`, gdy szablonu o tym `id` nie było."""
        raise NotImplementedError
