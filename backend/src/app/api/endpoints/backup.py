"""Endpoint HTTP /backup/trigger - ręczne wymuszenie kopii zapasowej przez API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_container, get_session
from app.container import Container

router = APIRouter()


@router.post("/backup/trigger")
async def trigger_backup(
    container: Annotated[Container, Depends(get_container)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Wymusza natychmiastowe utworzenie kopii zapasowej bazy danych."""
    logger.info("Żądanie ręcznego backupu przez API /backup/trigger")
    backup_service = container.backup_service(session)
    result_path = await backup_service.create_backup()
    return {"status": "ok", "backup_path": str(result_path)}
