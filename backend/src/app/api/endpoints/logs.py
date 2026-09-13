"""Endpoint HTTP /api/v1/logs - odpowiednik komendy /logs dla aplikacji mobilnej."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import EventOut, event_out
from app.container import Container

router = APIRouter()


@router.get("/logs", response_model=list[EventOut])
async def get_logs(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    include_sync: Annotated[bool, Query()] = True,
) -> list[EventOut]:
    """
    Zwraca ostatnie zdarzenia systemowe (widok "Ustawienia" w apce).

    `include_sync=false` pomija wpisy "Start/Koniec synchronizacji", które
    powstają co minutę i wypychają z listy wszystko inne.
    """
    events_service = container.events_service(session)
    events = await events_service.get_recent_events(limit, include_sync=include_sync)
    return [event_out(e) for e in events]
