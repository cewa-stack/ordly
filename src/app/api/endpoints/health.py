"""Endpoint HTTP /health - status aplikacji, alternatywny do komendy Telegram."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.container import Container

router = APIRouter()


@router.get("/health")
async def health_check(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """
    Zwraca status zdrowia aplikacji (ORDLY) w JSON.
    """
    health_service = container.health_service(session)
    status = await health_service.check()
    return {
        "uptime": status.uptime_human,
        "last_sync": status.last_sync_human,
        "database_ok": status.database_ok,
        "marketplace_connection_ok": status.marketplace_connection_ok,
    }
