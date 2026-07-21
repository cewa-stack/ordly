"""
Job APScheduler wysyłający przypomnienie o niewysłanych zamówieniach (20:00).

Funkcja jest celowo cienka - decyzja "czy i o czym przypomnieć" żyje
w ShippingReminderService, a formatowanie wiadomości w notifikatorze.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces.notifier import Notifier
from app.services.shipping_reminder_service import ShippingReminderService


async def run_shipping_reminder_job(
    session_scope_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    build_reminder_service: Callable[[AsyncSession], ShippingReminderService],
    notifier: Notifier,
) -> None:
    """
    Buduje przypomnienie i - jeśli jest potrzebne - wysyła je przez notifikator.

    Gdy serwis zwróci None (brak dzisiejszych zamówień lub wszystkie już
    wysłane), żadna wiadomość nie jest wysyłana.

    Args:
        session_scope_factory: Fabryka context managera sesji bazy danych.
        build_reminder_service: Funkcja budująca ShippingReminderService.
        notifier: Kanał wysyłki przypomnienia (Telegram).
    """
    try:
        async with session_scope_factory() as session:
            service = build_reminder_service(session)
            data = await service.build_reminder()

        if data is None:
            logger.info("Przypomnienie 20:00: brak zamówień wymagających wysyłki - pomijam")
            return

        await notifier.notify_shipping_reminder(data)
        logger.info(
            "Przypomnienie 20:00 wysłane: {} zamówień do wysłania z {} dzisiejszych",
            data.unshipped_count,
            data.orders_today,
        )
    except Exception:
        logger.exception("Zaplanowane przypomnienie o wysyłce nie powiodło się")
