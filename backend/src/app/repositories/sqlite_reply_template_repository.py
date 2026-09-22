"""Implementacja ReplyTemplateRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.reply_template_model import ReplyTemplateModel
from app.domain.entities.reply_template import ReplyTemplate
from app.domain.interfaces.reply_template_repository import ReplyTemplateRepository


class SqliteReplyTemplateRepository(ReplyTemplateRepository):
    """Dostęp do szablonów odpowiedzi przechowywanych w SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja.
        """
        self._session = session

    async def list_all(self) -> list[ReplyTemplate]:
        """Zwraca szablony po `position`, a przy remisie po kolejności dodania."""
        stmt = select(ReplyTemplateModel).order_by(
            ReplyTemplateModel.position, ReplyTemplateModel.id
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def add(self, title: str, body: str) -> ReplyTemplate:
        """Dodaje szablon na końcu listy."""
        last = await self._session.scalar(select(func.max(ReplyTemplateModel.position)))
        model = ReplyTemplateModel(title=title, body=body, position=(last or 0) + 1)
        self._session.add(model)
        # `flush`, nie `commit` - zatwierdza zakres sesji żądania, a `id`
        # jest potrzebne już teraz, w odpowiedzi.
        await self._session.flush()
        return self._to_domain(model)

    async def update(self, template_id: int, title: str, body: str) -> ReplyTemplate | None:
        """Zmienia tytuł i treść istniejącego szablonu."""
        model = await self._session.get(ReplyTemplateModel, template_id)
        if model is None:
            return None
        model.title = title
        model.body = body
        await self._session.flush()
        return self._to_domain(model)

    async def delete(self, template_id: int) -> bool:
        """Usuwa szablon o podanym `id`."""
        result = await self._session.execute(
            delete(ReplyTemplateModel).where(ReplyTemplateModel.id == template_id)
        )
        return (result.rowcount or 0) > 0

    @staticmethod
    def _to_domain(model: ReplyTemplateModel) -> ReplyTemplate:
        """Mapuje model ORM na encję domenową."""
        return ReplyTemplate(
            id=model.id,
            title=model.title,
            body=model.body,
            position=model.position,
        )
