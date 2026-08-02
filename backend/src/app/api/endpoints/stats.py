"""Endpoint HTTP /api/v1/stats - odpowiednik komendy /stats dla aplikacji mobilnej."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import StatsOut, stats_out
from app.container import Container

router = APIRouter()


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StatsOut:
    """Zwraca statystyki sprzedaży: dziś / w tym miesiącu / łącznie."""
    stats_service = container.stats_service(session)
    summary = await stats_service.get_summary()
    return stats_out(summary)
