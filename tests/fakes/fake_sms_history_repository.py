"""Fake implementacja SmsHistoryRepository - historia SMS w pamięci."""

from __future__ import annotations

from app.domain.entities.sms_message import SMS_STATUS_SENT, SmsRecord
from app.domain.interfaces.sms_history_repository import SmsHistoryRepository


class FakeSmsHistoryRepository(SmsHistoryRepository):
    """Przechowuje wpisy historii SMS w zwykłej liście."""

    def __init__(self) -> None:
        self.records: list[SmsRecord] = []

    async def was_sent_successfully(self, order_external_id: str, message_type: str) -> bool:
        return any(
            r.order_external_id == order_external_id
            and r.message_type == message_type
            and r.status == SMS_STATUS_SENT
            for r in self.records
        )

    async def record(self, record: SmsRecord) -> None:
        self.records.append(record)
