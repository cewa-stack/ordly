"""Serwis skrzynki - synchronizacja i odczyt maili od marketplace."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from loguru import logger

from app.core.config import MailWatchSettings
from app.domain.entities.mail_message import MailMessage
from app.domain.interfaces.mail_repository import MailRepository
from app.infrastructure.mail.imap_watcher import ImapConnectionError, ImapWatcher
from app.utils.time import utc_now

_FIRST_SYNC_LOOKBACK_DAYS = 7


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
        try:
            messages = await watcher.fetch_new_from_senders(
                self._settings.watch_senders, since
            )
        except ImapConnectionError:
            logger.exception("Synchronizacja skrzynki IMAP nie powiodła się")
            return 0

        new_count = 0
        for message in messages:
            if await self._mail_repository.exists(message.message_id):
                continue
            await self._mail_repository.save(message)
            new_count += 1
        return new_count

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
