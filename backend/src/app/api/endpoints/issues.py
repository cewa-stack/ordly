"""Endpointy HTTP /api/v1/issues/* - dyskusje i reklamacje pozakupowe."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.api.schemas import (
    IssueMessageOut,
    IssueOut,
    IssueReplyIn,
    issue_message_out,
    issue_out,
)
from app.container import Container

router = APIRouter()


@router.get("/issues", response_model=list[IssueOut])
async def list_issues(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[IssueOut]:
    """Zwraca aktualną listę dyskusji i reklamacji, pobraną na żywo z marketplace."""
    issues_service = container.issues_service(session)
    issues = await issues_service.list_issues()
    return [issue_out(i) for i in issues]


@router.get("/issues/{issue_id}/messages", response_model=list[IssueMessageOut])
async def get_issue_messages(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    issue_id: str,
) -> list[IssueMessageOut]:
    """Zwraca wątek wiadomości pojedynczej dyskusji/reklamacji, na żywo z marketplace."""
    issues_service = container.issues_service(session)
    messages = await issues_service.get_thread(issue_id)
    return [issue_message_out(m) for m in messages]


@router.post("/issues/{issue_id}/reply", status_code=204, response_model=None)
async def reply_to_issue(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
    issue_id: str,
    payload: IssueReplyIn,
) -> None:
    """Wysyła odpowiedź sprzedawcy w danej dyskusji/reklamacji."""
    issues_service = container.issues_service(session)
    await issues_service.reply(issue_id, payload.text)
