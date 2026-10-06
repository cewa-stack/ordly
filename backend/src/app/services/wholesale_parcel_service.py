"""
Jednorazowy alert o paczce od hurtowni F.H.P. MAIK-POL - pozycja z Notion
[FEAT-MAIL].

Skrzynkę czyta WYŁĄCZNIE backend na Raspberry Pi (W14): ten serwis
pracuje w jobie synchronizacji poczty, a desktop i telefon dostają tylko
gotowy alert (Control Hub przez MQTT, telefon przez Web Push).

Przebieg jednego cyklu:

1. IMAP: maile od `info@paczkomaty.pl` od ostatnio rozpatrzonego
   (pierwszy raz: z ostatnich 3 dni - decyzja M7-a).
2. Odrzucenie po nagłówkach wszystkiego, co nie jest „InPost -
   Potwierdzenie nadania przesyłki” - takie maile nie są nigdzie
   zapisywane (poza zakresem: przetwarzanie wszystkich maili InPost).
3. Dla nowego potwierdzenia nadania: pełna treść, rozpoznanie
   (`infrastructure/mail/inpost.py`), zapis wyniku w
   `processed_parcel_mails` - także gdy alertu nie ma, żeby nie dociągać
   tej samej treści w każdym cyklu.
4. Alert tylko dla paczki od F.H.P. MAIK-POL z jednoznacznym numerem,
   i tylko gdy mail nie jest starszy niż 3 dni (pierwsze uruchomienie
   nie budzi alertami o paczkach sprzed tygodnia).

Zdarzenia `WholesaleParcelShipped` publikuje `publish()` - wywoływane PO
zatwierdzeniu sesji, jak przy synchronizacji zamówień.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from loguru import logger

from app.core.config import MailWatchSettings
from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import WholesaleParcelShipped
from app.domain.entities.mail_message import MailMessage
from app.domain.entities.wholesale_parcel import WholesaleParcelNotice
from app.infrastructure.mail.imap_watcher import ImapConnectionError
from app.infrastructure.mail.inpost import (
    INPOST_SENDER_ADDRESS,
    OUTCOME_AMBIGUOUS_NUMBER,
    OUTCOME_NO_NUMBER,
    OUTCOME_OTHER_WHOLESALER,
    is_inpost_shipment_header,
    parse_parcel_mail,
)
from app.infrastructure.mail.mime import MailBodies
from app.repositories.sqlite_processed_parcel_mail_repository import ProcessedParcelMail
from app.services.mailbox_service import WatcherFactory, default_watcher_factory
from app.utils.time import utc_now

#: Pierwsze uruchomienie: tyle dni wstecz przeglądamy skrzynkę, i tylko
#: o tak świeżych mailach wychodzi alert (decyzja M7-a).
ALERT_WINDOW = timedelta(days=3)


class ProcessedParcelMailStore(Protocol):
    """Kontrakt zapisu rozpatrzonych maili (`SqliteProcessedParcelMailRepository`)."""

    async def exists(self, message_id: str) -> bool: ...

    async def latest_received_at(self) -> datetime | None: ...

    async def add(self, record: ProcessedParcelMail) -> None: ...


class WholesaleParcelService:
    """Wykrywa maile InPost o paczce od hurtowni i robi z nich jednorazowy alert."""

    def __init__(
        self,
        repository: ProcessedParcelMailStore,
        settings: MailWatchSettings,
        watcher_factory: WatcherFactory | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._watcher_factory = watcher_factory or default_watcher_factory(settings)
        self._event_bus = event_bus

    async def sync(self) -> list[WholesaleParcelNotice]:
        """
        Jeden cykl - zwraca alerty do opublikowania po zatwierdzeniu sesji.

        Brak połączenia ze skrzynką nie przerywa niczego: błąd trafia do
        logów, a kolejny cykl spróbuje ponownie.
        """
        if not self._settings.enabled:
            return []

        latest = await self._repository.latest_received_at()
        since = latest if latest is not None else utc_now() - ALERT_WINDOW
        try:
            messages = await self._watcher_factory().fetch_new_from_senders(
                [INPOST_SENDER_ADDRESS], since
            )
        except ImapConnectionError as exc:
            logger.error("Paczki od hurtowni: nie udało się sprawdzić skrzynki: {}", exc)
            return []

        notices: list[WholesaleParcelNotice] = []
        for message in messages:
            if not is_inpost_shipment_header(message):
                continue
            if await self._repository.exists(message.message_id):
                continue
            notice = await self._process(message)
            if notice is not None:
                notices.append(notice)
        return notices

    async def publish(self, notices: list[WholesaleParcelNotice]) -> None:
        """Publikuje alerty - PO zatwierdzeniu sesji, w której działało `sync()`."""
        if self._event_bus is None:
            return
        for notice in notices:
            await self._event_bus.publish(
                WholesaleParcelShipped(occurred_at=utc_now(), notice=notice)
            )

    async def _process(self, message: MailMessage) -> WholesaleParcelNotice | None:
        bodies = await self._bodies(message)
        if bodies is None:
            # Treść niedostępna (zerwane łącze) - mail NIE jest zapisywany,
            # więc następny cykl spróbuje jeszcze raz.
            return None

        result = parse_parcel_mail(message, bodies)
        fresh = message.received_at >= utc_now() - ALERT_WINDOW
        alerted = result.is_match and fresh

        if result.outcome in (OUTCOME_NO_NUMBER, OUTCOME_AMBIGUOUS_NUMBER):
            logger.error(
                "Paczki od hurtowni: mail {} od {} - nie da się jednoznacznie odczytać "
                "numeru paczki ({}), alert pominięty",
                message.message_id,
                result.wholesaler,
                result.outcome,
            )
        elif result.outcome == OUTCOME_OTHER_WHOLESALER:
            logger.info(
                "Paczki od hurtowni: mail {} dotyczy innego nadawcy ({}) - bez alertu",
                message.message_id,
                result.wholesaler or "nie rozpoznano",
            )
        elif result.is_match and not fresh:
            logger.info(
                "Paczki od hurtowni: paczka {} z maila sprzed ponad 3 dni - zapisana bez alertu",
                result.tracking_number,
            )
        elif result.is_match:
            logger.info(
                "Paczki od hurtowni: {} nadała paczkę {}",
                result.wholesaler,
                result.tracking_number,
            )

        await self._repository.add(
            ProcessedParcelMail(
                message_id=message.message_id,
                received_at=message.received_at,
                sender=message.sender,
                subject=message.subject,
                outcome=result.outcome,
                tracking_number=result.tracking_number,
                wholesaler=result.wholesaler,
                alerted=alerted,
            )
        )
        return result.notice if alerted else None

    async def _bodies(self, message: MailMessage) -> MailBodies | None:
        try:
            return await self._watcher_factory().fetch_bodies_by_message_id(message.message_id)
        except (ImapConnectionError, ValueError) as exc:
            logger.error(
                "Paczki od hurtowni: nie udało się pobrać treści maila {}: {}",
                message.message_id,
                exc,
            )
            return None
