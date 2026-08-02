"""Handler komendy /sync - wymuszenie natychmiastowej synchronizacji."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from app.bot.formatting import header
from app.container import Container
from app.domain.exceptions.domain_exceptions import MarketplaceUnavailableError

router = Router(name="sync")


@router.message(Command("sync"))
async def handle_sync(message: Message, container: Container) -> None:
    """
    Wymusza natychmiastową synchronizację zamówień, poza harmonogramem co 60s.

    Celowo NIE korzysta z sesji wstrzykiwanej przez middleware - otwiera
    własny zakres sesji i zamyka go (commit) PRZED publikacją zdarzeń,
    ponieważ subskrybenci OrderCreated/SyncFinished piszą do bazy we
    własnych sesjach i muszą widzieć zatwierdzone zamówienia.
    """
    await message.answer("⏳ Synchronizuję zamówienia...")

    try:
        async with container.session_scope() as session:
            sync_service = container.sync_orders_service(session)
            result = await sync_service.sync_new_orders()

        await sync_service.publish_sync_events(result)
        container.sync_status.mark_sync_completed()
    except MarketplaceUnavailableError:
        await message.answer(
            "Allegro API jest chwilowo niedostępne. Spróbuj ponownie później."
        )
        return
    except Exception:
        logger.exception("Błąd podczas ręcznej synchronizacji")
        await message.answer("Wystąpił błąd podczas synchronizacji.")
        return

    await message.answer(
        f"{header('✅', 'SYNCHRONIZACJA ZAKOŃCZONA')}\n\n"
        f"🆕 Nowe zamówienia: {result.new_orders_count}\n"
        f"🔍 Sprawdzone: {result.checked_orders_count}\n"
        f"❌ Anulowane: {len(result.cancelled_orders)}\n"
        f"↩️ Nowe zwroty: {len(result.new_returns)}"
    )
