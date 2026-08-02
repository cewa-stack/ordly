"""Endpoint HTTP /api/v1/returns - lista zwrotów klientów."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import ReturnOut, return_out
from app.container import Container

router = APIRouter()


@router.get("/returns", response_model=list[ReturnOut])
async def list_returns(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReturnOut]:
    """Zwraca listę ostatnich zwrotów klientów (paginacja: `limit`/`offset`)."""
    returns_service = container.returns_service(session)
    records = await returns_service.get_recent_returns(limit=limit, offset=offset)
    return [return_out(r) for r in records]
