"""
Endpointy HTTP /api/v1/reply-templates/* - szablony odpowiedzi w dyskusjach.

Czytają je obie aplikacje (pole odpowiedzi w Dyskusjach), a zmienia
wyłącznie desktop (Ustawienia -> Szablony odpowiedzi). Znaczniki w treści
podstawia aplikacja, bo to ona ma pod ręką wątek i zamówienie.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import ReplyTemplateIn, ReplyTemplateOut, reply_template_out
from app.container import Container

router = APIRouter()

_NOT_FOUND = "Nie ma takiego szablonu - mógł zostać usunięty na drugim urządzeniu."


@router.get("/reply-templates", response_model=list[ReplyTemplateOut])
async def list_reply_templates(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ReplyTemplateOut]:
    """Zwraca wszystkie szablony w kolejności wyświetlania."""
    repository = container.reply_template_repository(session)
    return [reply_template_out(t) for t in await repository.list_all()]


@router.post(
    "/reply-templates", response_model=ReplyTemplateOut, status_code=status.HTTP_201_CREATED
)
async def create_reply_template(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: ReplyTemplateIn,
) -> ReplyTemplateOut:
    """Dodaje szablon na końcu listy."""
    repository = container.reply_template_repository(session)
    return reply_template_out(await repository.add(payload.title, payload.body))


@router.put("/reply-templates/{template_id}", response_model=ReplyTemplateOut)
async def update_reply_template(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    template_id: int,
    payload: ReplyTemplateIn,
) -> ReplyTemplateOut:
    """Zmienia tytuł i treść szablonu."""
    repository = container.reply_template_repository(session)
    updated = await repository.update(template_id, payload.title, payload.body)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
    return reply_template_out(updated)


@router.delete(
    "/reply-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def delete_reply_template(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    template_id: int,
) -> None:
    """Usuwa szablon."""
    repository = container.reply_template_repository(session)
    if not await repository.delete(template_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
