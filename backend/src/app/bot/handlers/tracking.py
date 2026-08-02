"""Handler komendy /tracking [numer] - status przesyłki NA ŻĄDANIE."""

from __future__ import annotations

from aiogram import Router, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import header
from app.container import Container
from app.domain.exceptions.domain_exceptions import (
    MarketplaceUnavailableError,
    OrderNotFoundError,
    ShipmentNotAvailableError,
)

router = Router(name="tracking")


@router.message(Command("tracking"))
async def handle_tracking(
    message: Message, command: CommandObject, container: Container, session: AsyncSession
) -> None:
    """
    Pobiera i wyświetla aktualny status przesyłki.

    Zgodnie z wymaganiami projektu, status przesyłki NIE jest sprawdzany
    automatycznie przez scheduler - ta komenda jest jedynym miejscem,
    gdzie wykonywane jest zapytanie do Allegro o status przesyłki.
    """
    if not command.args:
        await message.answer("Podaj numer zamówienia: <code>/tracking 12345678</code>")
        return

    order_number = command.args.strip()
    tracking_service = container.tracking_service(session)

    await message.answer("⏳ Sprawdzam status przesyłki...")

    try:
        shipment = await tracking_service.get_current_tracking(order_number)
    except OrderNotFoundError:
        await message.answer(f"Nie znaleziono zamówienia o numerze {html.quote(order_number)}")
        return
    except ShipmentNotAvailableError:
        await message.answer(
            f"📦 Zamówienie {html.quote(order_number)} zostało opłacone, ale sprzedawca "
            "nie nadał jeszcze przesyłki. Sprawdź ponownie później."
        )
        return
    except MarketplaceUnavailableError:
        await message.answer(
            "Allegro API jest chwilowo niedostępne, a w bazie brak "
            "wcześniejszych danych o tej przesyłce. Spróbuj ponownie za chwilę."
        )
        return
    except Exception:
        logger.exception("Błąd podczas sprawdzania statusu przesyłki")
        await message.answer("Wystąpił nieoczekiwany błąd podczas sprawdzania przesyłki.")
        return

    updated_text = (
        shipment.updated_at.strftime("%Y-%m-%d %H:%M")
        if shipment.updated_at
        else "brak danych"
    )
    await message.answer(
        f"{header('🚚', f'PRZESYŁKA — {html.quote(order_number)}')}\n\n"
        f"🏢 Przewoźnik: {html.quote(shipment.carrier or 'brak danych')}\n"
        f"🔢 Numer: {html.quote(shipment.tracking_number or 'brak danych')}\n"
        f"📌 Status: {html.quote(shipment.status or 'brak danych')}\n"
        f"🕓 Aktualizacja: {updated_text}"
    )
