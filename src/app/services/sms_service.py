"""
Serwis wysyłki SMS do klienta - logika biznesowa powiadomień SMS.

Wywoływany wyłącznie przez subskrybenta Event Busa (zdarzenie
OrderPackingStarted), nigdy bezpośrednio z kontrolera czy schedulera.
Gwarantuje, że dany typ SMS wychodzi do klienta co najwyżej raz na
zamówienie, jest odporny na błędy bramki i zapisuje pełną historię.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from app.domain.entities.order import Order
from app.domain.entities.sms_message import (
    MESSAGE_TYPE_PACKING_STARTED,
    SMS_STATUS_FAILED,
    SMS_STATUS_SENT,
    SMS_STATUS_SKIPPED_NO_PHONE,
    SmsRecord,
)
from app.domain.interfaces.sms_history_repository import SmsHistoryRepository
from app.domain.interfaces.sms_provider import SmsProvider
from app.utils.time import utc_now

# Treść SMS wysyłanego, gdy zamówienie wchodzi w etap pakowania.
PACKING_STARTED_TEXT = (
    "Dziękujemy za złożenie zamówienia ❤️ Właśnie rozpoczęliśmy jego "
    "pakowanie. Po nadaniu przesyłki otrzymasz kolejną informację.\n\n"
    "Miłego dnia!"
)


@dataclass(frozen=True, slots=True)
class SmsOutcome:
    """
    Wynik obsługi żądania wysyłki SMS.

    `sent=False` wraz z `skipped_reason` wyjaśnia, dlaczego SMS nie
    wyszedł (brak numeru, już wysłany wcześniej, błąd bramki).
    """

    sent: bool
    skipped_reason: str | None = None


class SmsService:
    """Wysyła SMS do klienta z gwarancją jednorazowości i odpornością na błędy."""

    def __init__(
        self,
        provider: SmsProvider,
        history_repository: SmsHistoryRepository,
    ) -> None:
        """
        Args:
            provider: Bramka SMS (realna lub testowa - LoggingSmsProvider).
            history_repository: Historia wysyłek (audyt + ochrona przed dublem).
        """
        self._provider = provider
        self._history = history_repository

    async def send_packing_started(self, order: Order) -> SmsOutcome:
        """
        Wysyła SMS informujący o rozpoczęciu pakowania zamówienia.

        Kolejność zabezpieczeń:
        1. Brak numeru telefonu -> SMS pominięty, zdarzenie zapisane w historii.
        2. SMS tego typu już wysłany -> pominięty (jednorazowość).
        3. Bramka rzuca wyjątek -> wyjątek zapisany, próba oznaczona jako
           nieudana, proces realizacji NIE jest przerywany.
        """
        return await self._send(
            order=order,
            message_type=MESSAGE_TYPE_PACKING_STARTED,
            text=PACKING_STARTED_TEXT,
        )

    async def _send(self, order: Order, message_type: str, text: str) -> SmsOutcome:
        """Wspólna ścieżka wysyłki z ochroną przed dublem i historią."""
        phone = order.buyer.phone_number
        if not phone:
            logger.info(
                "Zamówienie {} nie ma numeru telefonu - SMS ({}) pominięty",
                order.external_id,
                message_type,
            )
            await self._record(
                order,
                message_type,
                None,
                SMS_STATUS_SKIPPED_NO_PHONE,
                "Brak numeru telefonu w danych zamówienia",
            )
            return SmsOutcome(sent=False, skipped_reason="no_phone")

        already_sent = await self._history.was_sent_successfully(
            order.external_id, message_type
        )
        if already_sent:
            logger.debug(
                "SMS ({}) dla zamówienia {} już wysłany - pomijam",
                message_type,
                order.external_id,
            )
            return SmsOutcome(sent=False, skipped_reason="already_sent")

        try:
            result = await self._provider.send(phone, text)
        except Exception as exc:
            logger.exception(
                "Bramka SMS ({}) zgłosiła wyjątek dla zamówienia {}",
                self._provider.provider_code,
                order.external_id,
            )
            await self._record(
                order, message_type, phone, SMS_STATUS_FAILED, f"Wyjątek bramki: {exc}"
            )
            return SmsOutcome(sent=False, skipped_reason="provider_error")

        if not result.success:
            logger.warning(
                "Bramka SMS odrzuciła wiadomość dla zamówienia {}: {}",
                order.external_id,
                result.error,
            )
            await self._record(order, message_type, phone, SMS_STATUS_FAILED, result.error)
            return SmsOutcome(sent=False, skipped_reason="provider_failed")

        logger.info(
            "Wysłano SMS ({}) do klienta zamówienia {}",
            message_type,
            order.external_id,
        )
        await self._record(
            order, message_type, phone, SMS_STATUS_SENT, result.provider_message_id
        )
        return SmsOutcome(sent=True)

    async def _record(
        self,
        order: Order,
        message_type: str,
        phone: str | None,
        status: str,
        detail: str | None,
    ) -> None:
        """Zapisuje wynik próby wysyłki w historii SMS."""
        await self._history.record(
            SmsRecord(
                order_external_id=order.external_id,
                message_type=message_type,
                phone=phone,
                status=status,
                detail=detail,
                occurred_at=utc_now(),
            )
        )
