"""
Katalog powiadomień push ORDLY - jedyne miejsce, które decyduje, JAK
brzmi powiadomienie i jak jest zbudowane.

Źródłem jest `ordly-powiadomienia-push.html`, sekcje 03 (katalog) i 04
(zasady). Trzy reguły są tu wymuszone konstrukcyjnie, nie przez dobre
chęci:

1. **Akcje tylko do odczytu.** `PushPayload` nie ma pola pozwalającego
   dołożyć akcję zmieniającą dane - dostępne są wyłącznie "Pokaż"
   i "Wycisz na godzinę". Telefon pokazuje, desktop robi.
2. **Treść zawsze z liczbą.** Każdy builder przyjmuje konkretne
   wartości (kwota, sztuki, ile zostało czasu) i wplata je w treść.
   Nie ma buildera dla "masz nowe zdarzenie w systemie".
3. **Grupowanie po wątku.** `thread` to jedna z sześciu stałych wartości,
   która trafia do `tag` powiadomienia - iOS grupuje po aplikacji,
   ORDLY dokłada podział per typ zdarzenia.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import time
from decimal import Decimal
from typing import Literal

# Wątki grupowania z sekcji 04 - nazwa wątku zastępuje nazwę aplikacji
# w nagłówku powiadomienia na iOS.
PushThread = Literal["orders", "stock", "issues", "returns", "mail", "sync"]

# Godziny ciszy z sekcji 04. Powiadomienie wysłane w tym oknie leci bez
# dźwięku i wibracji - ale LECI, bo Web Push nie ma kolejki "do rana",
# a przetrzymywanie go po stronie Pi znaczyłoby, że po restarcie usługi
# przepada bez śladu.
QUIET_HOURS_START = time(22, 0)
QUIET_HOURS_END = time(7, 0)

_ACTION_SHOW = {"action": "open", "title": "Pokaż"}
_ACTION_MUTE = {"action": "mute", "title": "Wycisz na godzinę"}


def is_quiet_hour(now: time) -> bool:
    """
    Czy podana godzina wypada w oknie ciszy 22:00-7:00.

    Okno przechodzi przez północ, więc warunek jest sumą dwóch
    przedziałów, a nie zwykłym `start <= now <= end`.
    """
    return now >= QUIET_HOURS_START or now < QUIET_HOURS_END


@dataclass(frozen=True, slots=True)
class PushPayload:
    """
    Jedno powiadomienie gotowe do wysłania.

    `url` to ścieżka w aplikacji mobilnej, którą otworzy akcja "Pokaż" -
    zawsze prowadzi do PODGLĄDU rekordu, nigdy do formularza akcji.
    `badge` niesie liczbę spraw wymagających decyzji na desktopie;
    `None` oznacza "nie zmieniaj plakietki" (np. przy cichym
    potwierdzeniu z hurtowni).

    ROZNICA WOBEC KONCEPCJI, ktora jest pisana pod natywny iOS: tam
    `thread-id` GRUPUJE powiadomienia w stos. W Web Push (a ORDLY Mobile
    to PWA) odpowiednik, czyli `tag`, dziala inaczej - ZASTEPUJE
    poprzednie powiadomienie o tym samym tagu. Dlatego rozdzielamy dwa
    pojecia:

    - `thread` - do czego zdarzenie nalezy; trafia do `data`, uzywane
      przez aplikacje do grupowania na wlasnej liscie powiadomien,
    - `collapse_key` - czy nowe powiadomienie ma ZASTAPIC poprzednie.

    Zbiorcze "4 nowe zamowienia" ma zastepowac wczesniejsze "3 nowe
    zamowienia" (ten sam klucz), ale dwa rozne niskie stany maja obok
    siebie zostac (klucz per SKU).
    """

    title: str
    body: str
    thread: PushThread
    url: str
    silent: bool = False
    badge: int | None = None
    collapse_key: str | None = None
    actions: list[dict[str, str]] = field(default_factory=lambda: [_ACTION_SHOW, _ACTION_MUTE])

    def to_json(self) -> str:
        """Serializuje payload do postaci, którą rozumie `sw.js` w aplikacji mobilnej."""
        return json.dumps(
            {
                "title": self.title,
                "body": self.body,
                "tag": self.collapse_key or self.thread,
                "thread": self.thread,
                "url": self.url,
                "silent": self.silent,
                "badge": self.badge,
                "actions": self.actions,
            },
            ensure_ascii=False,
        )


#: Separator tysięcy to NIEŁAMLIWA spacja (U+00A0), nie zwykła - dokładnie
#: taka, jaką daje `Intl.NumberFormat("pl-PL")` w aplikacji desktopowej.
#: Zwykła spacja pozwoliłaby złamać `2 340,00 zł` na końcu linii
#: powiadomienia i rozbić kwotę na dwie linijki. Nie zamieniaj jej na " "
#: przy porządkach w kodzie.
_THOUSANDS_SEPARATOR = " "


def _money(amount: Decimal, currency: str = "PLN") -> str:
    """
    Kwota w formacie z sekcji 7.2 specyfikacji UI: `249,90 zł`,
    z niełamliwą spacją jako separatorem tysięcy.

    Powiadomienie jest często jedynym miejscem, gdzie użytkownik widzi
    kwotę tego dnia - musi wyglądać tak samo jak w aplikacji.
    """
    suffix = "zł" if currency.upper() == "PLN" else currency
    formatted = f"{amount:,.2f}".replace(",", _THOUSANDS_SEPARATOR).replace(".", ",")
    return f"{formatted} {suffix}"


def _shorten(text: str, limit: int = 80) -> str:
    """Skraca listę pozycji - w powiadomieniu liczy się skala, nie pełny spis."""
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


# --------------------------------------------------------------------------
# Katalog - sekcja 03. Czego tu nie ma, tego się nie wysyła.
# --------------------------------------------------------------------------


def new_order(
    *,
    marketplace: str,
    buyer_login: str,
    amount: Decimal,
    currency: str,
    products_summary: str,
    external_id: str,
    badge: int | None = None,
    silent: bool = False,
) -> PushPayload:
    """Nowe zamówienie - natychmiast. „Nowe zamówienie · Allegro"."""
    return PushPayload(
        title=f"Nowe zamówienie · {marketplace.capitalize()}",
        body=f"{buyer_login} — {_money(amount, currency)}. {_shorten(products_summary)}",
        thread="orders",
        url=f"/orders/{external_id}",
        silent=silent,
        badge=badge,
        collapse_key=f"order:{external_id}",
    )


def many_new_orders(
    *,
    count: int,
    per_channel: dict[str, int],
    total_amount: Decimal,
    currency: str,
    badge: int | None = None,
    silent: bool = False,
) -> PushPayload:
    """
    Wiele zamówień naraz - zbiorczo zamiast serii osobnych powiadomień.

    Rozbicie na kanały jest istotne: „4 nowe zamówienia" bez informacji
    skąd przyszły nie mówi nic o tym, gdzie szukać problemu.
    """
    breakdown = ", ".join(
        f"{channel.capitalize()} ({n})" if n > 1 else channel.capitalize()
        for channel, n in sorted(per_channel.items(), key=lambda item: -item[1])
    )
    return PushPayload(
        title=f"{count} {_orders_word(count)}",
        body=f"{breakdown} — łącznie {_money(total_amount, currency)}.",
        thread="orders",
        url="/orders",
        silent=silent,
        badge=badge,
    )


def low_stock(
    *,
    name: str,
    sku: str,
    stock: int,
    min_stock: int,
    silent: bool = False,
) -> PushPayload:
    """Niski stan - natychmiast. Produkt, ile zostało, przy jakim progu."""
    return PushPayload(
        title="Niski stan",
        body=f"{name} — zostały {stock} szt. przy progu {min_stock}.",
        thread="stock",
        url=f"/stock/{sku}",
        silent=silent,
        collapse_key=f"stock:{sku}",
    )


def unanswered_question(
    *,
    buyer_login: str,
    subject: str,
    hours_left: int | None,
    issue_id: str,
    badge: int | None = None,
    silent: bool = False,
) -> PushPayload:
    """
    Pytanie kupującego bez odpowiedzi - natychmiast.

    `hours_left` to czas do limitu odpowiedzi narzuconego przez kanał.
    Gdy go nie znamy, treść po prostu go pomija - lepiej niż zmyślona
    liczba godzin.
    """
    deadline = f" Zostało {hours_left} godz." if hours_left is not None else ""
    return PushPayload(
        title="Pytanie bez odpowiedzi",
        body=f"{buyer_login} pyta: {_shorten(subject, 60)}.{deadline}",
        thread="issues",
        url=f"/issues/{issue_id}",
        silent=silent,
        badge=badge,
        collapse_key=f"issue:{issue_id}",
    )


def new_return(
    *,
    external_id: str,
    products_summary: str,
    reason: str,
    badge: int | None = None,
    silent: bool = False,
) -> PushPayload:
    """Nowy zwrot do decyzji - natychmiast. Numer, produkt, powód."""
    return PushPayload(
        title="Nowy zwrot do decyzji",
        body=f"#{external_id[:8].upper()} {_shorten(products_summary, 50)} — {reason}.",
        thread="returns",
        url=f"/returns/{external_id}",
        silent=silent,
        badge=badge,
        collapse_key=f"return:{external_id}",
    )


def sync_failed(
    *,
    channel: str,
    healthy_channels: int,
    retry_in_minutes: int,
    silent: bool = False,
) -> PushPayload:
    """
    Błąd synchronizacji - dopiero po DRUGIEJ nieudanej próbie.

    Treść trzyma się tonu z sekcji 7.3: co się stało, co mimo to
    zadziałało, kiedy kolejna próba. Bez przeprosin.
    """
    survived = (
        f"Pozostałe {healthy_channels} kanały zaktualizowane. "
        if healthy_channels > 0
        else "Żaden inny kanał nie był aktywny. "
    )
    return PushPayload(
        title=f"{channel.capitalize()} nie odpowiedziało",
        body=f"{survived}Ordi spróbuje ponownie za {retry_in_minutes} minut.",
        thread="sync",
        url="/settings",
        silent=silent,
        collapse_key=f"sync:{channel.lower()}",
    )


def wholesaler_confirmed(
    *,
    wholesaler_name: str,
    items_summary: str,
) -> PushPayload:
    """
    Odpowiedź hurtowni - CICHE z definicji (sekcja 03).

    Potwierdzenie wysyłki nie wymaga reakcji, więc nie budzi telefonu
    i nie rusza plakietki.
    """
    return PushPayload(
        title=f"{wholesaler_name} potwierdziła wysyłkę",
        body=_shorten(items_summary, 90),
        thread="mail",
        url="/mailbox",
        silent=True,
        actions=[_ACTION_SHOW],
    )


def pending_packing(
    *,
    count: int,
    oldest_since: str,
    badge: int | None = None,
    silent: bool = False,
) -> PushPayload:
    """Zaległe pakowanie - raz dziennie o 9:00. Od kiedy czeka najstarsze."""
    return PushPayload(
        title=f"{count} {_orders_word(count, genitive=True)} do spakowania",
        body=f"Najstarsze czeka od {oldest_since}.",
        thread="orders",
        url="/orders",
        silent=silent,
        badge=badge,
    )


def _orders_word(n: int, *, genitive: bool = False) -> str:
    """
    Polska odmiana „zamówienie" po liczebniku.

    Bez tego powiadomienia brzmią jak tłumaczenie maszynowe
    („4 nowe zamówienie"), co przy czymś, co wyskakuje na ekranie
    blokady kilka razy dziennie, rzuca się w oczy natychmiast.
    """
    if n == 1:
        return "zamówienie" if genitive else "nowe zamówienie"
    few = n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14)
    if genitive:
        return "zamówienia" if few else "zamówień"
    return "nowe zamówienia" if few else "nowych zamówień"
