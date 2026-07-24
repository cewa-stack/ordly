"""
Endpointy HTTP /api/v1/push/* - subskrypcja Web Push dla TOOM Mobile
uruchomionego jako PWA (drugi kanał powiadomień obok bota Telegram,
patrz docs/01_app.md sekcja Web Push).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    PushSubscriptionIn,
    PushUnsubscribeIn,
    VapidPublicKeyOut,
)
from app.container import Container
from app.domain.entities.push_subscription import PushSubscription
from app.utils.time import utc_now

router = APIRouter()


@router.get("/push/vapid-public-key", response_model=VapidPublicKeyOut)
async def get_vapid_public_key(
    container: Annotated[Container, Depends(get_container)],
) -> VapidPublicKeyOut:
    """
    Zwraca klucz publiczny VAPID potrzebny przeglądarce do
    `PushManager.subscribe({applicationServerKey: ...})`.

    `enabled=False` (brak kluczy w `.env`) oznacza, że backend jeszcze
    nie ma skonfigurowanego Web Push - apka powinna ukryć tę opcję
    zamiast próbować subskrybować z pustym kluczem.
    """
    public_key, enabled = container.web_push_status()
    return VapidPublicKeyOut(public_key=public_key, enabled=enabled)


@router.post(
    "/push/subscribe", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def subscribe(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: PushSubscriptionIn,
) -> None:
    """Zapisuje (lub odnawia) subskrypcję Web Push jednego urządzenia/przeglądarki."""
    repository = container.push_subscription_repository(session)
    await repository.add(
        PushSubscription(
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            created_at=utc_now(),
        )
    )


@router.delete(
    "/push/subscribe", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def unsubscribe(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: PushUnsubscribeIn,
) -> None:
    """Usuwa subskrypcję Web Push (np. przy wyłączeniu powiadomień w Ustawieniach)."""
    repository = container.push_subscription_repository(session)
    await repository.delete_by_endpoint(payload.endpoint)


@router.post("/push/test", response_model=dict)
async def send_test_push(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """
    Wysyła testowe powiadomienie do wszystkich zapisanych subskrypcji -
    przycisk "Wyślij testowe powiadomienie" w Ustawieniach apki.
    """
    notifier = container.web_push_notifier()
    if notifier is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Web Push nie jest skonfigurowany na backendzie (brak kluczy VAPID w .env).",
        )

    repository = container.push_subscription_repository(session)
    subscriptions = await repository.get_all()
    if not subscriptions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Brak aktywnych subskrypcji - włącz powiadomienia push w Ustawieniach najpierw.",
        )

    await notifier.send_text("To jest testowe powiadomienie z TOOM.")
    return {"status": "ok", "sent_to": len(subscriptions)}
