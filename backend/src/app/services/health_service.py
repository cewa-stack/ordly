"""Serwis sprawdzania stanu zdrowia aplikacji dla komendy /health."""

from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces.marketplace_plugin import MarketplacePlugin
from app.shared.dto.stats_dto import HealthStatus
from app.utils.time import utc_now

_START_TIME = utc_now()


class SyncStatus:
    """
    Współdzielony znacznik czasu ostatniej udanej synchronizacji.

    Żyje przez cały czas działania aplikacji (jedna instancja w kontenerze
    DI) - dzięki temu HealthService może być tworzony per żądanie, bez
    trzymania długowiecznej sesji bazy danych.
    """

    def __init__(self) -> None:
        self._last_sync_at: datetime | None = None

    def mark_sync_completed(self) -> None:
        """Aktualizuje znacznik czasu ostatniej udanej synchronizacji."""
        self._last_sync_at = utc_now()

    @property
    def last_sync_at(self) -> datetime | None:
        """Zwraca czas ostatniej udanej synchronizacji lub None, jeśli brak."""
        return self._last_sync_at


class HealthService:
    """Sprawdza stan bazy danych, połączenia z marketplace oraz uptime."""

    def __init__(
        self,
        session: AsyncSession,
        plugin: MarketplacePlugin,
        sync_status: SyncStatus,
    ) -> None:
        """
        Args:
            session: Sesja bazy danych bieżącego żądania.
            plugin: Aktywny plugin marketplace.
            sync_status: Współdzielony znacznik ostatniej synchronizacji.
        """
        self._session = session
        self._plugin = plugin
        self._sync_status = sync_status

    async def check(self) -> HealthStatus:
        """Wykonuje szybkie sprawdzenie stanu kluczowych zależności."""
        database_ok = await self._check_database()
        marketplace_ok = await self._check_marketplace()

        uptime = utc_now() - _START_TIME
        last_sync_at = self._sync_status.last_sync_at
        last_sync_human = (
            last_sync_at.strftime("%Y-%m-%d %H:%M") if last_sync_at else "jeszcze nie wykonano"
        )

        return HealthStatus(
            uptime_human=_format_timedelta(uptime),
            last_sync_human=last_sync_human,
            database_ok=database_ok,
            marketplace_connection_ok=marketplace_ok,
        )

    async def _check_database(self) -> bool:
        """Weryfikuje, że baza danych odpowiada na proste zapytanie."""
        try:
            await self._session.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("Sprawdzenie zdrowia bazy danych nie powiodło się")
            return False

    async def _check_marketplace(self) -> bool:
        """Weryfikuje, że token dostępowy marketplace jest ważny lub odświeżalny."""
        try:
            return await self._plugin.check_connection()
        except Exception:
            logger.exception("Sprawdzenie połączenia z marketplace nie powiodło się")
            return False


def _format_timedelta(delta: timedelta) -> str:
    """Formatuje czas trwania na czytelny tekst w języku polskim."""
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}min"
