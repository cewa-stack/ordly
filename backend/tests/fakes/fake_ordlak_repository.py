"""Fake implementacja OrdlakRepository - działa w pamięci, bez bazy danych."""

from __future__ import annotations

from dataclasses import replace

from app.domain.entities.ordlak_generation import OrdlakGeneration
from app.domain.interfaces.ordlak_repository import OrdlakRepository


class FakeOrdlakRepository(OrdlakRepository):
    """Historia generacji trzymana w słowniku - do testów jednostkowych."""

    def __init__(self) -> None:
        self._items: dict[int, OrdlakGeneration] = {}
        self._next_id = 1

    async def save(self, generation: OrdlakGeneration) -> OrdlakGeneration:
        saved = replace(generation, id=self._next_id)
        self._items[self._next_id] = saved
        self._next_id += 1
        return saved

    async def get_by_id(self, generation_id: int) -> OrdlakGeneration | None:
        return self._items.get(generation_id)

    async def get_recent(self, limit: int = 20, offset: int = 0) -> list[OrdlakGeneration]:
        items = sorted(self._items.values(), key=lambda g: g.created_at, reverse=True)
        return items[offset : offset + limit]

    async def update_final_texts(
        self, generation_id: int, final_title: str, final_description_html: str
    ) -> OrdlakGeneration | None:
        existing = self._items.get(generation_id)
        if existing is None:
            return None
        updated = replace(
            existing,
            final_title=final_title,
            final_description_html=final_description_html,
        )
        self._items[generation_id] = updated
        return updated
