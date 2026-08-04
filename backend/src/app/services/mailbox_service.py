"""Serwis skrzynki - synchronizacja i odczyt maili od marketplace."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from loguru import logger

from app.core.config import MailWatchSettings
from app.domain.entities.mail_message import MailMessage
from app.domain.interfaces.mail_repository import MailRepository
from app.infrastructure.mail.imap_watcher import ImapConnectionError, ImapWatcher
from app.utils.time import utc_now

_FIRST_SYNC_LOOKBACK_DAYS = 7


@dataclass(frozen=True, slots=True)
class MailboxStatus:
    """
    Stan skrzynki do pokazania w aplikacji.

    Istnieje po to, żeby pusta lista maili nie była niemym "brak
    wiadomości" - użytkownik musi widzieć różnicę między "IMAP nie jest
    skonfigurowany na Pi", "skonfigurowany, ale nic nie przyszło" i
    "logowanie IMAP nie działa". Nie zawiera hasła ani pełnego adresu -
    `user_masked` pokazuje tylko tyle, żeby dało się rozpoznać konto.
    """

    configured: bool
    host: str
    user_masked: str
    watch_senders: list[str]
    message_count: int
    last_received_at: datetime | None


def _mask_user(user: str) -> str:
    """Zamienia `sklep@gmail.com` na `sk***@gmail.com` - do rozpoznania, nie do skopiowania."""
    if not user:
        return ""
    local, _, domain = user.partition("@")
    visible = local[:2]
    masked = f"{visible}***" if len(local) > 2 else f"{local}***"
    return f"{masked}@{domain}" if domain else masked


class MailWatcherProtocol(Protocol):
    """Kontrakt watchera IMAP - pozwala podmienić realny ImapWatcher fake'iem w testach."""

    async def fetch_new_from_senders(
        self, senders: list[str], since: datetime
    ) -> list[MailMessage]: ...


WatcherFactory = Callable[[], MailWatcherProtocol]


def _default_watcher_factory(settings: MailWatchSettings) -> WatcherFactory:
    def factory() -> MailWatcherProtocol:
        return ImapWatcher(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password.get_secret_value(),
        )

    return factory


class MailboxService:
    """
    Synchronizuje metadane maili (IMAP -> SQLite) i udostępnia je do
    wyświetlenia. Pełna treść maila NIE jest cache'owana - `body_preview`
    wystarcza do listy, a szczegóły są out of scope tego serwisu (patrz
    dokumentacja modułu appplans_06: "cache'ować tylko podgląd").
    """

    def __init__(
        self,
        mail_repository: MailRepository,
        settings: MailWatchSettings,
        watcher_factory: WatcherFactory | None = None,
    ) -> None:
        """
        Args:
            mail_repository: Repozytorium zapisanych maili.
            settings: Konfiguracja IMAP.
            watcher_factory: Fabryka watchera - domyślnie tworzy prawdziwy
                `ImapWatcher`, nadpisywalna w testach fake'iem (bez
                monkeypatchowania), analogicznie do `MailService.send_fn`.
        """
        self._mail_repository = mail_repository
        self._settings = settings
        self._watcher_factory = watcher_factory or _default_watcher_factory(settings)

    async def sync_new_mail(self) -> int:
        """
        Sprawdza skrzynkę i zapisuje nowo wykryte maile.

        Zwraca liczbę nowo zapisanych maili. Nic nie robi (zwraca 0),
        gdy IMAP nie jest skonfigurowany - to nie jest błąd, tylko
        funkcja świadomie wyłączona do czasu konfiguracji w `.env`.

        Wariant dla schedulera: awaria IMAP jest logowana i połykana,
        bo cykliczny job nie ma komu jej pokazać. Wersja dla ręcznego
        wyzwolenia z aplikacji to `sync_now()` - tam błąd LECI dalej,
        bo użytkownik stoi przy przycisku i czeka na odpowiedź.
        """
        try:
            return await self.sync_now()
        except ImapConnectionError:
            logger.exception("Synchronizacja skrzynki IMAP nie powiodła się")
            return 0

    async def sync_now(self) -> int:
        """
        Jak `sync_new_mail`, ale przepuszcza `ImapConnectionError` dalej.

        Używane przez `POST /api/v1/mail/sync` - gdy logowanie IMAP nie
        działa, użytkownik musi zobaczyć powód, a nie ciche "0 nowych".

        Raises:
            ImapConnectionError: Gdy połączenie/logowanie IMAP zawiedzie.
        """
        if not self._settings.enabled:
            return 0

        latest = await self._mail_repository.get_latest_received_at()
        since = (
            latest
            if latest is not None
            else utc_now() - timedelta(days=_FIRST_SYNC_LOOKBACK_DAYS)
        )

        watcher = self._watcher_factory()
        messages = await watcher.fetch_new_from_senders(self._settings.watch_senders, since)

        new_count = 0
        for message in messages:
            if await self._mail_repository.exists(message.message_id):
                continue
            await self._mail_repository.save(message)
            new_count += 1
        return new_count

    async def get_status(self) -> MailboxStatus:
        """Zwraca stan skrzynki (konfiguracja + liczniki) do diagnostyki w aplikacji."""
        return MailboxStatus(
            configured=self._settings.enabled,
            host=self._settings.host,
            user_masked=_mask_user(self._settings.user),
            watch_senders=self._settings.watch_senders,
            message_count=await self._mail_repository.count(),
            last_received_at=await self._mail_repository.get_latest_received_at(),
        )

    async def list_messages(
        self,
        source: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MailMessage]:
        """Zwraca ostatnie maile (opcjonalnie filtrowane po źródle/nieprzeczytane)."""
        return await self._mail_repository.get_recent(
            source=source, unread_only=unread_only, limit=limit, offset=offset
        )

    async def mark_read(self, message_id: str) -> None:
        """Oznacza mail jako przeczytany."""
        await self._mail_repository.mark_read(message_id)
