"""
Zależności FastAPI (Depends) - odpowiednik middleware DI z bota,
dostosowany do natywnego mechanizmu wstrzykiwania FastAPI.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Container


def get_container(request: Request) -> Container:
    """
    Zwraca kontener DI zapisany w stanie aplikacji FastAPI przy starcie.

    Args:
        request: Żądanie HTTP, z którego pobierany jest kontener
            przypięty do `app.state.container` w main.py.
    """
    return request.app.state.container


async def get_session(
    request: Request,
) -> AsyncGenerator[AsyncSession]:
    """Otwiera sesję bazy danych na czas obsługi jednego żądania HTTP."""
    container: Container = request.app.state.container
    async with container.session_scope() as session:
        yield session
