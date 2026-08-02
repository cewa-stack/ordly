"""
Serwis tworzenia i zarządzania kopiami zapasowymi bazy SQLite.

Używa natywnej komendy SQLite `VACUUM INTO`, która tworzy spójną,
atomową kopię pliku bazy danych nawet podczas aktywnego zapisu przez
inne połączenia (scheduler, bot).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus.bus import EventBus
from app.core.event_bus.events import BackupCreated
from app.utils.time import utc_now


class BackupService:
    """Tworzy kopie zapasowe bazy danych i zarządza ich retencją."""

    def __init__(
        self,
        session: AsyncSession,
        backup_directory: Path,
        retention_days: int,
        event_bus: EventBus,
    ) -> None:
        """
        Args:
            session: Aktywna sesja SQLAlchemy (używana do wykonania VACUUM INTO).
            backup_directory: Katalog docelowy kopii zapasowych.
            retention_days: Liczba dni, po których stare kopie są usuwane.
            event_bus: Magistrala zdarzeń do publikacji BackupCreated.
        """
        self._session = session
        self._backup_directory = backup_directory
        self._retention_days = retention_days
        self._event_bus = event_bus

    async def create_backup(self) -> Path:
        """
        Tworzy nową, spójną kopię zapasową bazy danych.

        Returns:
            Ścieżka do utworzonego pliku kopii zapasowej.
        """
        self._backup_directory.mkdir(parents=True, exist_ok=True)
        timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
        backup_path = self._backup_directory / f"ordly_{timestamp}.db"

        try:
            await self._session.execute(
                text("VACUUM INTO :backup_path"),
                {"backup_path": str(backup_path)},
            )
            logger.info("Kopia zapasowa utworzona: {}", backup_path)
        except Exception:
            logger.exception("Nie udało się utworzyć kopii zapasowej bazy danych")
            raise

        await self._event_bus.publish(
            BackupCreated(occurred_at=utc_now(), backup_path=str(backup_path))
        )

        await self._cleanup_old_backups()
        return backup_path

    async def _cleanup_old_backups(self) -> None:
        """Usuwa kopie zapasowe starsze niż skonfigurowany okres retencji."""
        cutoff = utc_now() - timedelta(days=self._retention_days)
        removed_count = 0

        for backup_file in self._backup_directory.glob("ordly_*.db"):
            file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime, UTC).replace(
                tzinfo=None
            )
            if file_mtime < cutoff:
                backup_file.unlink()
                removed_count += 1

        if removed_count > 0:
            logger.info(
                "Usunięto {} przeterminowanych kopii zapasowych (starszych niż {} dni)",
                removed_count,
                self._retention_days,
            )

    def list_backups(self) -> list[Path]:
        """Zwraca listę dostępnych kopii zapasowych posortowaną od najnowszej."""
        if not self._backup_directory.exists():
            return []
        return sorted(
            self._backup_directory.glob("ordly_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
