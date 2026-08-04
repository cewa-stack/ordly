"""Endpointy HTTP /api/v1/mail/* - wysyłka do hurtowni (SMTP) i skrzynka (IMAP)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    MailboxStatusOut,
    MailMessageOut,
    MailSyncResultOut,
    WholesalerMailIn,
    mail_message_out,
    mailbox_status_out,
)
from app.container import Container
from app.infrastructure.mail.imap_watcher import ImapConnectionError

router = APIRouter()


@router.post("/mail/send-wholesaler-order", status_code=204, response_model=None)
async def send_wholesaler_order(
    container: Annotated[Container, Depends(get_container)],
    payload: WholesalerMailIn,
) -> None:
    """
    Wysyła mail zamówienia do hurtowni.

    Aplikacja desktopowa układa temat/treść (dane hurtowni, lista
    produktów, ilości) - ten endpoint tylko wysyła gotowy tekst przez
    SMTP skonfigurowany na Pi.
    """
    mail_service = container.mail_service()
    await mail_service.send(payload.to, payload.subject, payload.body)


@router.get("/mail/messages", response_model=list[MailMessageOut])
async def list_mail_messages(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    source: Annotated[str | None, Query()] = None,
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MailMessageOut]:
    """Zwraca listę maili od marketplace wykrytych przez skrzynkę (Skrzynka)."""
    mailbox_service = container.mailbox_service(session)
    messages = await mailbox_service.list_messages(
        source=source, unread_only=unread_only, limit=limit, offset=offset
    )
    return [mail_message_out(m) for m in messages]


@router.get("/mail/status", response_model=MailboxStatusOut)
async def get_mailbox_status(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MailboxStatusOut:
    """
    Zwraca stan skrzynki: czy IMAP jest skonfigurowany, kogo obserwuje
    i ile maili leży w bazie.

    Bez tego pusta lista maili była nierozróżnialna od niedziałającej
    konfiguracji - aplikacja pokazywała "brak wiadomości" niezależnie
    od tego, czy IMAP w ogóle był włączony.
    """
    mailbox_service = container.mailbox_service(session)
    return mailbox_status_out(await mailbox_service.get_status())


@router.post("/mail/sync", response_model=MailSyncResultOut)
async def sync_mailbox(
    container: Annotated[Container, Depends(get_container)],
) -> MailSyncResultOut:
    """
    Wymusza natychmiastowe sprawdzenie skrzynki IMAP.

    Otwiera własny zakres sesji (tak jak `POST /orders/sync`), żeby
    zapis nowych maili był zatwierdzony przed odpowiedzią. Błąd
    połączenia/logowania IMAP wraca jako 502 z treścią do pokazania
    użytkownikowi - w cyklicznym jobie taki błąd jest tylko logowany,
    ale przy ręcznym kliknięciu użytkownik musi znać powód.
    """
    async with container.session_scope() as session:
        mailbox_service = container.mailbox_service(session)
        status = await mailbox_service.get_status()
        if not status.configured:
            return MailSyncResultOut(new_count=0, configured=False)
        try:
            new_count = await mailbox_service.sync_now()
        except ImapConnectionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return MailSyncResultOut(new_count=new_count, configured=True)


@router.post("/mail/messages/{message_id}/mark-read", status_code=204, response_model=None)
async def mark_mail_message_read(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    message_id: str,
) -> None:
    """Oznacza mail jako przeczytany."""
    mailbox_service = container.mailbox_service(session)
    await mailbox_service.mark_read(message_id)
