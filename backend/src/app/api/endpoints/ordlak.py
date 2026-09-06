"""
Endpointy HTTP /api/v1/ordlak/* - asystent ORDLY.

Cztery rzeczy: stan modułu, zadanie pytania oraz odczyt i kasowanie
zapisanych wątków. Logika mieszka w `ordlak_assistant_service`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    OrdlakChatIn,
    OrdlakChatOut,
    OrdlakConversationOut,
    OrdlakStatusOut,
    ordlak_chat_out,
    ordlak_conversation_out,
)
from app.container import Container
from app.services.ordlak_assistant_service import (
    OrdlakConversationNotFoundError,
    OrdlakError,
    OrdlakNotConfiguredError,
)

router = APIRouter()


@router.get("/ordlak/status", response_model=OrdlakStatusOut)
async def get_ordlak_status(
    container: Annotated[Container, Depends(get_container)],
) -> OrdlakStatusOut:
    """
    Zwraca stan modułu: czy klucz API jest ustawiony i na jakim modelu chodzi.

    Ekran Ordlaka pyta o to przed pokazaniem pola tekstowego, żeby od razu
    powiedzieć "brak klucza na Pi" zamiast pozwolić napisać pytanie
    i dopiero wtedy pokazać błąd.
    """
    settings = container.ordlak_settings()
    return OrdlakStatusOut(configured=settings.enabled, model=settings.model)


@router.post("/ordlak/chat", response_model=OrdlakChatOut)
async def chat_with_assistant(
    container: Annotated[Container, Depends(get_container)],
    payload: OrdlakChatIn,
) -> OrdlakChatOut:
    """
    Zadaje pytanie asystentowi i zapisuje rozmowę.

    Otwiera własny zakres sesji (jak `POST /orders/sync`), żeby obie
    wypowiedzi były zatwierdzone przed odpowiedzią - inaczej
    `conversation_id` w odpowiedzi wskazywałby na wątek, którego nie ma
    jeszcze w bazie, i kolejne pytanie dostałoby 404.
    """
    async with container.session_scope() as session:
        service = container.ordlak_assistant_service(session)
        try:
            result = await service.ask(payload.message, payload.conversation_id)
        except OrdlakNotConfiguredError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        except OrdlakConversationNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except OrdlakError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

    return ordlak_chat_out(result)


@router.get("/ordlak/conversations", response_model=list[OrdlakConversationOut])
async def list_conversations(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[OrdlakConversationOut]:
    """Zwraca zapisane wątki (bez treści), od ostatnio używanego."""
    service = container.ordlak_assistant_service(session)
    return [
        ordlak_conversation_out(conversation)
        for conversation in await service.conversations(limit=limit)
    ]


@router.get("/ordlak/conversations/{conversation_id}", response_model=OrdlakConversationOut)
async def get_conversation(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    conversation_id: int,
) -> OrdlakConversationOut:
    """Zwraca jeden wątek z pełną historią wiadomości."""
    service = container.ordlak_assistant_service(session)
    conversation = await service.conversation(conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rozmowa o numerze {conversation_id} nie istnieje.",
        )
    return ordlak_conversation_out(conversation)


@router.delete("/ordlak/conversations/{conversation_id}", status_code=204, response_model=None)
async def delete_conversation(
    container: Annotated[Container, Depends(get_container)],
    conversation_id: int,
) -> None:
    """Usuwa wątek razem z wiadomościami. 404, gdy nie było czego usuwać."""
    async with container.session_scope() as session:
        service = container.ordlak_assistant_service(session)
        if not await service.delete_conversation(conversation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rozmowa o numerze {conversation_id} nie istnieje.",
            )
