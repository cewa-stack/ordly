"""
Endpointy HTTP /api/v1/push/* - subskrypcja Web Push dla ORDLY Mobile
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


@router.post("/push/subscribe", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
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


@router.delete("/push/subscribe", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
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
) -> dict:
    """
    Wysyła testowe powiadomienie do wszystkich zapisanych subskrypcji -
    przycisk "Wyślij testowe powiadomienie" w Ustawieniach apki.

    `sent_to` to liczba urządzeń, których serwer push (Apple/Google)
    PRZYJĄŁ powiadomienie - nie liczba wierszy w bazie. Martwe subskrypcje
    (np. starego telefonu) są przy okazji usuwane i zwracane jako
    `expired`, żeby aplikacja mogła to powiedzieć wprost.
    """
    notifier = container.web_push_notifier()
    if notifier is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Web Push nie jest skonfigurowany na backendzie (brak kluczy VAPID w .env).",
        )

    report = await notifier.send_test()
    if report.subscriptions == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Brak aktywnych subskrypcji - włącz powiadomienia push w Ustawieniach najpierw.",
        )
    if report.delivered == 0:
        detail = (
            "Żadne urządzenie nie przyjęło powiadomienia - subskrypcje wygasły i zostały "
            "usunięte. Wyłącz i włącz powiadomienia ponownie na tym telefonie."
            if report.failed == 0
            else "Serwer powiadomień odrzucił wysyłkę - szczegóły w logach usługi ordly na Pi "
            "(journalctl -u ordly -n 50)."
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    return {
        "status": "ok",
        "sent_to": report.delivered,
        "expired": report.expired,
        "failed": report.failed,
    }
