"""Repozytorium przetworzonych maili InPost o paczkach od hurtowni ([FEAT-MAIL])."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.processed_parcel_mail_model import ProcessedParcelMailModel


@dataclass(frozen=True, slots=True)
class ProcessedParcelMail:
    """Jeden rozpatrzony mail i jego wynik."""

    message_id: str
    received_at: datetime
    sender: str
    subject: str
    outcome: str
    tracking_number: str | None
    wholesaler: str | None
    alerted: bool


class SqliteProcessedParcelMailRepository:
    """Zapis i odczyt `processed_parcel_mails`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, message_id: str) -> bool:
        stmt = select(func.count()).where(ProcessedParcelMailModel.message_id == message_id)
        return ((await self._session.execute(stmt)).scalar_one() or 0) > 0

    async def latest_received_at(self) -> datetime | None:
        stmt = select(func.max(ProcessedParcelMailModel.received_at))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add(self, record: ProcessedParcelMail) -> None:
        self._session.add(
            ProcessedParcelMailModel(
                message_id=record.message_id,
                received_at=record.received_at,
                sender=record.sender,
                subject=record.subject,
                outcome=record.outcome,
                tracking_number=record.tracking_number,
                wholesaler=record.wholesaler,
                alerted=record.alerted,
            )
        )
        await self._session.flush()

    async def get(self, message_id: str) -> ProcessedParcelMail | None:
        model = await self._session.get(ProcessedParcelMailModel, message_id)
        if model is None:
            return None
        return ProcessedParcelMail(
            message_id=model.message_id,
            received_at=model.received_at,
            sender=model.sender,
            subject=model.subject,
            outcome=model.outcome,
            tracking_number=model.tracking_number,
            wholesaler=model.wholesaler,
            alerted=model.alerted,
        )
