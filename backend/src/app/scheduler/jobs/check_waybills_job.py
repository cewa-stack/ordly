"""
Job APScheduler wywoływany cyklicznie co N sekund.

Cienki wrapper na wzór sync_orders_job.py - cała logika żyje
w WaybillCheckService. Awaria (Allegro niedostępne albo inny wyjątek)
nie ma osobnego alertu push - ten sam problem sieciowy zgłosi już
sync_orders_job, który działa częściej.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.waybill_check_service import WaybillCheckService


async def run_check_waybills_job(
    session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    build_waybill_check_service: Callable[[AsyncSession], WaybillCheckService],
) -> None:
    """Wykonuje jeden cykl sprawdzania nowych numerów przesyłek."""
    try:
        async with session_scope_factory() as session:
            service = build_waybill_check_service(session)
            detected = await service.check_new_waybills()
        if detected:
            logger.info("Wykryto {} nowych numerów przesyłek", detected)
    except Exception:
        logger.exception("Nieoczekiwany błąd podczas sprawdzania numerów przesyłek")
