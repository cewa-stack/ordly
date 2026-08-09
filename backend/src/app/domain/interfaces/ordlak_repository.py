"""Kontrakt dostępu do historii generacji Ordlaka, niezależny od bazy danych."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.ordlak_generation import OrdlakGeneration


class OrdlakRepository(ABC):
    """Serwis zależy wyłącznie od tego interfejsu - implementacja SQLite w repositories/."""

    @abstractmethod
    async def save(self, generation: OrdlakGeneration) -> OrdlakGeneration:
        """Zapisuje generację i zwraca ją z nadanym `id`."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, generation_id: int) -> OrdlakGeneration | None:
        """Zwraca pojedynczą generację albo None, gdy nie istnieje."""
        raise NotImplementedError

    @abstractmethod
    async def get_recent(self, limit: int = 20, offset: int = 0) -> list[OrdlakGeneration]:
        """Zwraca historię generacji, najnowsze pierwsze."""
        raise NotImplementedError

    @abstractmethod
    async def update_final_texts(
        self, generation_id: int, final_title: str, final_description_html: str
    ) -> OrdlakGeneration | None:
        """
        Zapisuje ręcznie poprawiony tytuł/opis. Zwraca None, gdy generacja
        o tym `id` nie istnieje - endpoint zamienia to na 404.
        """
        raise NotImplementedError
