"""Implementacja MailRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.mail_message_model import MailMessageModel
from app.domain.entities.mail_message import MailMessage
from app.domain.interfaces.mail_repository import MailRepository


class SqliteMailRepository(MailRepository):
    """Dostęp do wykrytych maili przechowywanych w SQLite przez SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, message_id: str) -> bool:
        stmt = (
            select(func.count())
            .select_from(MailMessageModel)
            .where(MailMessageModel.message_id == message_id)
        )
        result = await self._session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def save(self, message: MailMessage) -> None:
        model = MailMessageModel(
            message_id=message.message_id,
            sender=message.sender,
            subject=message.subject,
            received_at=message.received_at,
            source=message.source,
            body_preview=message.body_preview,
            is_read=message.is_read,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_recent(
        self,
        source: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MailMessage]:
        stmt = select(MailMessageModel).order_by(MailMessageModel.received_at.desc())
        if source:
            stmt = stmt.where(MailMessageModel.source == source)
        if unread_only:
            stmt = stmt.where(MailMessageModel.is_read.is_(False))
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_by_id(self, message_id: str) -> MailMessage | None:
        stmt = select(MailMessageModel).where(MailMessageModel.message_id == message_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def mark_read(self, message_id: str) -> None:
        stmt = (
            update(MailMessageModel)
            .where(MailMessageModel.message_id == message_id)
            .values(is_read=True)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_latest_received_at(self) -> datetime | None:
        stmt = select(func.max(MailMessageModel.received_at))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _to_domain(model: MailMessageModel) -> MailMessage:
        return MailMessage(
            message_id=model.message_id,
            sender=model.sender,
            subject=model.subject,
            received_at=model.received_at,
            source=model.source,
            body_preview=model.body_preview,
            is_read=model.is_read,
        )
