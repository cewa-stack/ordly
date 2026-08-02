"""Endpoint HTTP /api/v1/dashboard - podsumowanie na ekran Start aplikacji mobilnej."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import DashboardOut, dashboard_out
from app.container import Container

router = APIRouter()


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DashboardOut:
    """
    Zwraca zagregowane dane na ekran Start: sprzedaż dziś, zamówienia do
    wysłania, produkty poniżej minimum i status ostatniej synchronizacji.
    """
    dashboard_service = container.dashboard_service(session)
    health_service = container.health_service(session)

    summary = await dashboard_service.get_summary()
    health = await health_service.check()

    return dashboard_out(summary, health)
