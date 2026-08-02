"""Implementacja SmsHistoryRepository oparta o SQLAlchemy + SQLite."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.sms_message_model import SmsMessageModel
from app.domain.entities.sms_message import SMS_STATUS_SENT, SmsRecord
from app.domain.interfaces.sms_history_repository import SmsHistoryRepository


class SqliteSmsHistoryRepository(SmsHistoryRepository):
    """Zapisuje i odczytuje historię wiadomości SMS z SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy, wstrzykiwana per operacja
                przez Dependency Injection.
        """
        self._session = session

    async def was_sent_successfully(self, order_external_id: str, message_type: str) -> bool:
        """Sprawdza istnienie skutecznej wysyłki danego typu przez COUNT."""
        stmt = (
            select(func.count())
            .select_from(SmsMessageModel)
            .where(
                SmsMessageModel.order_external_id == order_external_id,
                SmsMessageModel.message_type == message_type,
                SmsMessageModel.status == SMS_STATUS_SENT,
            )
        )
        result = await self._session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    async def record(self, record: SmsRecord) -> None:
        """Zapisuje wynik próby wysyłki SMS w historii."""
        self._session.add(
            SmsMessageModel(
                order_external_id=record.order_external_id,
                message_type=record.message_type,
                phone=record.phone,
                status=record.status,
                detail=record.detail,
                created_at=record.occurred_at,
            )
        )
        await self._session.flush()
