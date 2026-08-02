"""
Konfiguracja silnika i sesji SQLAlchemy (async).

Ten moduł jest jedynym miejscem, gdzie tworzony jest silnik
połączenia z bazą danych. Repozytoria i serwisy otrzymują sesję
przez Dependency Injection (nigdy nie tworzą jej same) - to
umożliwia łatwe podmienienie bazy w testach.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """
    Tworzy silnik asynchronicznego połączenia z bazą danych.

    Włącza tryb WAL (Write-Ahead Logging) dla SQLite - pozwala na
    współbieżny odczyt podczas zapisu, co jest krytyczne przy tej
    architekturze (scheduler pisze co 60s, jednocześnie bot/API czytają).

    Args:
        settings: Konfiguracja bazy danych (URL, echo).

    Returns:
        Skonfigurowany silnik AsyncEngine gotowy do użycia.
    """
    logger.info("Inicjalizacja silnika bazy danych: {}", settings.database_url)
    engine = create_async_engine(
        settings.database_url,
        echo=settings.echo,
        connect_args={"timeout": 30},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_wal_mode(dbapi_connection, connection_record) -> None:
        """Włącza WAL mode i optymalizacje na każdym nowym połączeniu SQLite."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-8000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """
    Tworzy fabrykę sesji powiązaną z danym silnikiem.

    Args:
        engine: Silnik bazy danych utworzony przez create_engine().

    Returns:
        Fabryka sesji (async_sessionmaker) do wstrzykiwania w DI.
    """
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )
