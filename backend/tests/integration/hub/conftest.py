"""Wspólne narzędzia testów ORDLy Control Hub: prawdziwa baza SQLite w pliku."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database.base import Base

SessionScope = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def make_database(path: Path) -> tuple[AsyncEngine, SessionScope]:
    """
    Plik SQLite zamiast `:memory:` - serwis Huba otwiera osobną sesję na
    każdą operację, a baza w pamięci żyje tylko w jednym połączeniu.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def session_scope() -> AsyncIterator[AsyncSession]:
        session = factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    return engine, session_scope


class RecordingPublisher:
    """Zapisuje wiadomości zamiast wysyłać je do brokera."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, Any], bool]] = []

    async def publish(self, topic: str, payload: dict[str, Any], retain: bool = False) -> bool:
        # Przez JSON, jak po kablu - wartości nie do zserializowania wyszłyby tu, nie na Pi.
        self.messages.append((topic, json.loads(json.dumps(payload)), retain))
        return True

    def on(self, topic: str) -> list[dict[str, Any]]:
        return [payload for t, payload, _ in self.messages if t == topic]


@pytest_asyncio.fixture
async def session_scope(tmp_path: Path) -> AsyncGenerator[SessionScope]:
    engine, scope = await make_database(tmp_path / "hub.db")
    yield scope
    await engine.dispose()
