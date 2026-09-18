"""
Handler komendy /stock - podgląd magazynu ORDLY z poziomu czatu.

Podkomendy:
    /stock           - wszystkie oferty razem z ilością na półce
    /stock [fraza]   - tylko oferty pasujące do frazy

Komenda TYLKO CZYTA. Ilość wpisuje się w aplikacji desktopowej, gdzie
widać obok siebie zdjęcie, cenę i historię wpisów - czyli to, z czego
człowiek korzysta, licząc towar na półce. Wpisywanie liczb z telefonu
przez czat dawałoby te same dane bez żadnego z tych zabezpieczeń.
"""

from __future__ import annotations

from aiogram import Router, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import header
from app.container import Container
from app.domain.entities.marketplace_offer import MarketplaceOffer

router = Router(name="stock")

#: Ile ofert zmieści się w jednej wiadomości, żeby Telegram jej nie uciął.
_MAX_OFFERS = 30


@router.message(Command("stock"))
async def handle_stock(
    message: Message, command: CommandObject, container: Container, session: AsyncSession
) -> None:
    """Pokazuje oferty magazynu, opcjonalnie zawężone podaną frazą."""
    query = (command.args or "").strip()

    try:
        service = container.offer_catalog_service(session)
        offers = await service.get_offers()
    except Exception:
        logger.exception("Błąd podczas obsługi komendy /stock")
        await message.answer("Wystąpił błąd podczas odczytu magazynu.")
        return

    if query:
        needle = query.lower()
        offers = [
            offer
            for offer in offers
            if needle in offer.name.lower() or needle in (offer.signature or "").lower()
        ]

    if not offers:
        await message.answer(
            f"Brak ofert pasujących do <b>{html.quote(query)}</b>."
            if query
            else "Magazyn jest pusty. Zsynchronizuj listę ofert w aplikacji."
        )
        return

    lines = [_format_offer(offer) for offer in offers[:_MAX_OFFERS]]
    if len(offers) > _MAX_OFFERS:
        lines.append(f"…oraz {len(offers) - _MAX_OFFERS} dalszych ofert.")

    title = f"MAGAZYN - {query.upper()}" if query else "MAGAZYN"
    await message.answer(f"{header('📦', title)}\n\n" + "\n\n".join(lines))


def _format_offer(offer: MarketplaceOffer) -> str:
    """
    Jedna oferta w wiadomości Telegrama.

    Kreska zamiast zera przy `quantity_on_hand`: "nigdy nie liczyłem"
    i "policzyłem, nie ma" to dwie różne odpowiedzi na pytanie "ile mam".
    """
    on_hand = "—" if offer.quantity_on_hand is None else f"{offer.quantity_on_hand} szt."
    line = f"<b>{html.quote(offer.name)}</b>\n   Na półce: {on_hand}"
    if offer.price is not None:
        line += f" | Cena: {offer.price:.2f} zł"
    return f"{line}\n   W ofercie: {offer.available_stock} szt. | {offer.marketplace}"
