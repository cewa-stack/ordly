"""
Handler komendy /stock - Inventory Management System (IMS).

Podkomendy:
    /stock                      - aktualny stan magazynu
    /stock new SKU nazwa        - dodaj nowy produkt do magazynu
    /stock set SKU ilość        - ustaw stan magazynowy
    /stock add SKU ilość        - zwiększ stan (np. dostawa)
    /stock remove SKU ilość     - zmniejsz stan (korekta)
    /stock min SKU ilość        - ustaw minimalny stan (próg ostrzeżeń)
    /stock history [SKU]        - historia zmian magazynowych
    /stock buy                  - lista zakupów (produkty poniżej minimum)
    /stock report               - raport magazynowy z prognozą
    /stock link OFERTA SKU [n]  - przypisz składnik oferty (zestawy)
    /stock unlink OFERTA        - usuń mapowanie oferty
    /stock parent SKU GŁÓWNY    - podprodukt schodzący razem z produktem głównym
"""

from __future__ import annotations

from aiogram import Router, html
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import header
from app.container import Container
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.exceptions.domain_exceptions import (
    DuplicateInventoryItemError,
    InsufficientStockError,
    InventoryItemNotFoundError,
)
from app.services.inventory_service import InventoryService

router = Router(name="stock")

_USAGE_TEXT = (
    f"{header('📦', 'MAGAZYN - UŻYCIE')}\n\n"
    "/stock — stan magazynu\n"
    "/stock new [SKU] [nazwa] — nowy produkt\n"
    "/stock set [SKU] [ilość] — ustaw stan\n"
    "/stock add [SKU] [ilość] — zwiększ stan\n"
    "/stock remove [SKU] [ilość] — zmniejsz stan\n"
    "/stock min [SKU] [ilość] — minimalny stan\n"
    "/stock history [SKU] — historia zmian\n"
    "/stock buy — lista zakupów\n"
    "/stock report — raport magazynowy\n"
    "/stock link [oferta] [SKU] [ilość] — składnik oferty\n"
    "/stock unlink [oferta] — usuń mapowanie oferty\n"
    "/stock parent [SKU] [produkt główny] — podprodukt (- odłącza)"
)


@router.message(Command("stock"))
async def handle_stock(
    message: Message, command: CommandObject, container: Container, session: AsyncSession
) -> None:
    """Rozdziela podkomendy /stock i deleguje do funkcji pomocniczych."""
    inventory_service = container.inventory_service(session)
    args = (command.args or "").split()

    try:
        if not args:
            await _show_overview(message, inventory_service)
            return

        subcommand = args[0].lower()
        if subcommand == "new":
            await _create_item(message, inventory_service, args[1:])
        elif subcommand in ("set", "add", "remove", "min"):
            await _change_stock(message, inventory_service, subcommand, args[1:])
        elif subcommand == "history":
            await _show_history(message, inventory_service, args[1:])
        elif subcommand == "buy":
            await _show_shopping_list(message, inventory_service)
        elif subcommand == "report":
            await _show_report(message, inventory_service)
        elif subcommand == "link":
            await _link_offer(message, inventory_service, args[1:])
        elif subcommand == "unlink":
            await _unlink_offer(message, inventory_service, args[1:])
        elif subcommand == "parent":
            await _set_parent(message, inventory_service, args[1:])
        else:
            await message.answer(_USAGE_TEXT)
    except InventoryItemNotFoundError as exc:
        await message.answer(
            f"Nie znaleziono produktu o SKU <code>{html.quote(exc.sku)}</code>. "
            "Sprawdź /stock lub dodaj go: /stock new [SKU] [nazwa]"
        )
    except DuplicateInventoryItemError as exc:
        await message.answer(
            f"Produkt o SKU <code>{html.quote(exc.sku)}</code> już istnieje w magazynie."
        )
    except InsufficientStockError as exc:
        await message.answer(
            f"Nie można zdjąć {exc.requested} szt. produktu "
            f"<code>{html.quote(exc.sku)}</code> - dostępne {exc.available} szt."
        )
    except ValueError as exc:
        await message.answer(str(exc))
    except Exception:
        logger.exception("Błąd podczas obsługi komendy /stock")
        await message.answer("Wystąpił błąd podczas obsługi magazynu.")


async def _show_overview(message: Message, service: InventoryService) -> None:
    """Wyświetla aktualny stan wszystkich produktów magazynowych."""
    items = await service.get_stock_overview()
    if not items:
        await message.answer(
            "Magazyn jest pusty. Dodaj pierwszy produkt:\n"
            "<code>/stock new PET60 Butelka PET 60 ml</code>"
        )
        return

    lines = [
        f"{item.status_emoji} <b>{html.quote(item.name)}</b>\n"
        f"   SKU: <code>{html.quote(item.sku)}</code> | Stan: {item.stock} szt."
        for item in items
    ]
    await message.answer(f"{header('📦', 'MAGAZYN')}\n\n" + "\n\n".join(lines))


async def _create_item(message: Message, service: InventoryService, args: list[str]) -> None:
    """Tworzy nowy produkt magazynowy: /stock new SKU nazwa."""
    if len(args) < 2:
        await message.answer(
            "Podaj SKU i nazwę: <code>/stock new PET60 Butelka PET 60 ml</code>"
        )
        return

    sku = args[0]
    name = " ".join(args[1:])
    item = await service.create_item(sku, name)
    await message.answer(
        f"✅ Dodano produkt <b>{html.quote(item.name)}</b> "
        f"(SKU: <code>{html.quote(item.sku)}</code>).\n"
        f"Ustaw stan: <code>/stock set {html.quote(item.sku)} 100</code>\n"
        f"Ustaw minimum: <code>/stock min {html.quote(item.sku)} 20</code>"
    )


async def _change_stock(
    message: Message, service: InventoryService, subcommand: str, args: list[str]
) -> None:
    """Obsługuje /stock set|add|remove|min SKU ilość."""
    if len(args) != 2 or not args[1].lstrip("-").isdigit():
        await message.answer(f"Podaj SKU i ilość: <code>/stock {subcommand} PET60 100</code>")
        return

    sku = args[0]
    quantity = int(args[1])

    if subcommand == "set":
        item = await service.set_stock(sku, quantity)
        summary = f"Ustawiono stan: {item.stock} szt."
    elif subcommand == "add":
        item = await service.add_stock(sku, quantity)
        summary = f"Dodano {quantity} szt. Nowy stan: {item.stock} szt."
    elif subcommand == "remove":
        item = await service.remove_stock(sku, quantity)
        summary = f"Zdjęto {quantity} szt. Nowy stan: {item.stock} szt."
    else:
        item = await service.set_min_stock(sku, quantity)
        summary = f"Minimalny stan: {item.min_stock} szt."

    warning = ""
    if subcommand != "min" and item.is_low_stock:
        warning = (
            f"\n\n⚠️ Uwaga! Pozostało {item.stock} szt. "
            f"(minimum: {item.min_stock}). Rozważ zamówienie nowej dostawy."
        )

    await message.answer(
        f"{item.status_emoji} <b>{html.quote(item.name)}</b>\n{summary}{warning}"
    )


def _format_movement(movement: InventoryMovement) -> str:
    """Formatuje jeden wpis historii magazynowej."""
    sign = "+" if movement.change >= 0 else ""
    reference = f" ({html.quote(movement.reference)})" if movement.reference else ""
    return (
        f"{movement.occurred_at.strftime('%d.%m.%Y %H:%M')} | "
        f"<b>{html.quote(movement.item_sku)}</b> {sign}{movement.change} "
        f"→ {movement.stock_after} szt.\n"
        f"   Powód: {html.quote(movement.reason)}{reference}"
    )


async def _show_history(message: Message, service: InventoryService, args: list[str]) -> None:
    """Wyświetla historię zmian magazynowych: /stock history [SKU]."""
    sku = args[0] if args else None
    movements = await service.get_history(sku, limit=10)
    if not movements:
        await message.answer("Brak zapisanych zmian magazynowych.")
        return

    title = f"HISTORIA — {sku}" if sku else "HISTORIA MAGAZYNU"
    body = "\n\n".join(_format_movement(m) for m in movements)
    await message.answer(f"{header('📜', html.quote(title))}\n\n{body}")


async def _show_shopping_list(message: Message, service: InventoryService) -> None:
    """Wyświetla listę zakupów - produkty poniżej minimalnego stanu."""
    items = await service.get_shopping_list()
    if not items:
        await message.answer("🛒 Lista zakupów jest pusta - wszystkie stany w normie.")
        return

    lines = [
        f"✔ {html.quote(item.name)} — {item.stock} szt. (min. {item.min_stock})"
        for item in items
    ]
    await message.answer(f"{header('🛒', 'PRODUKTY DO ZAMÓWIENIA')}\n\n" + "\n".join(lines))


async def _show_report(message: Message, service: InventoryService) -> None:
    """Wyświetla raport magazynowy z prognozą wyczerpania zapasów."""
    report = await service.get_report()
    if report.total_items == 0:
        await message.answer("Magazyn jest pusty - brak danych do raportu.")
        return

    sections = [
        f"{header('📊', 'RAPORT MAGAZYNOWY')}\n",
        f"📦 Liczba produktów: {report.total_items}",
        f"💰 Wartość magazynu: {report.total_stock_value:.2f} PLN",
    ]

    if report.low_stock_items:
        lines = "\n".join(
            f"   🔴 {html.quote(i.name)} — {i.stock} szt. (min. {i.min_stock})"
            for i in report.low_stock_items
        )
        sections.append(f"\n⚠️ <b>Niski stan</b>\n{lines}")

    if report.forecasts:
        lines = "\n".join(
            f"   ⏳ {html.quote(f.name)} — {f.avg_daily_sales:.1f} szt./dzień, "
            f"zapas na ok. {f.days_left} dni"
            for f in report.forecasts[:10]
        )
        sections.append(f"\n📈 <b>Prognoza zapasów (30 dni)</b>\n{lines}")

    if report.items_without_sales:
        lines = "\n".join(
            f"   💤 {html.quote(i.name)}" for i in report.items_without_sales[:10]
        )
        sections.append(f"\n🚫 <b>Bez sprzedaży (30 dni)</b>\n{lines}")

    if report.recent_movements:
        lines = "\n\n".join(_format_movement(m) for m in report.recent_movements[:5])
        sections.append(f"\n📜 <b>Ostatnie zmiany</b>\n\n{lines}")

    await message.answer("\n".join(sections))


async def _link_offer(message: Message, service: InventoryService, args: list[str]) -> None:
    """Przypisuje składnik magazynowy do oferty: /stock link OFERTA SKU [ilość]."""
    if len(args) not in (2, 3) or (len(args) == 3 and not args[2].isdigit()):
        await message.answer(
            "Podaj ofertę, SKU i opcjonalnie ilość:\n"
            "<code>/stock link 12345678 PET60 2</code>\n"
            "Dla zestawu powtórz komendę dla każdego składnika."
        )
        return

    external_product_id = args[0]
    sku = args[1]
    quantity = int(args[2]) if len(args) == 3 else 1
    await service.link_offer("allegro", external_product_id, sku, quantity)
    await message.answer(
        f"🔗 Oferta <code>{html.quote(external_product_id)}</code> → "
        f"{quantity} × <code>{html.quote(sku)}</code>.\n"
        "Sprzedaż tej oferty będzie automatycznie zdejmować składnik z magazynu."
    )


async def _set_parent(message: Message, service: InventoryService, args: list[str]) -> None:
    """
    Wiąże podprodukt z produktem głównym: /stock parent SKU GŁÓWNY.

    Myślnik w miejscu produktu głównego zdejmuje powiązanie. To jedyny
    sposób, żeby zrobić to z czatu - a przydatny, bo podprodukt znika
    z listy magazynowej w aplikacji desktopowej.
    """
    if len(args) != 2:
        await message.answer(
            "Podaj SKU podproduktu i SKU produktu głównego:\n"
            "<code>/stock parent NAK10 BUT10</code>\n"
            "Myślnik odłącza: <code>/stock parent NAK10 -</code>"
        )
        return

    sku, parent = args[0], args[1]
    if parent == "-":
        await service.set_parent(sku, None)
        await message.answer(
            f"🔓 <code>{html.quote(sku)}</code> jest znowu samodzielnym produktem."
        )
        return

    item = await service.set_parent(sku, parent)
    sub_items = await service.get_sub_items(parent)
    ile = "podprodukt" if len(sub_items) == 1 else "podprodukty"
    await message.answer(
        f"🔗 <code>{html.quote(item.sku)}</code> schodzi teraz razem z "
        f"<code>{html.quote(parent)}</code> (razem {len(sub_items)} {ile}).\n"
        "Sprzedaż produktu głównego zdejmie tyle samo sztuk podproduktu. "
        "Ręczne korekty stanu ich nie ruszają."
    )


async def _unlink_offer(message: Message, service: InventoryService, args: list[str]) -> None:
    """Usuwa mapowanie oferty: /stock unlink OFERTA."""
    if len(args) != 1:
        await message.answer("Podaj numer oferty: <code>/stock unlink 12345678</code>")
        return

    removed = await service.unlink_offer("allegro", args[0])
    if removed == 0:
        await message.answer(f"Oferta <code>{html.quote(args[0])}</code> nie miała mapowania.")
    else:
        await message.answer(
            f"🗑 Usunięto {removed} składnik(i) oferty <code>{html.quote(args[0])}</code>."
        )
