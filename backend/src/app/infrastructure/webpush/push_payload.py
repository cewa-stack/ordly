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
import re
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from typing import Literal
from urllib.parse import quote

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


_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """
    Usuwa znaczniki HTML z treści przeznaczonej pod Web Push.

    Ten kanał nie renderuje HTML - w przeciwieństwie do Telegrama, gdzie
    bot ustawia `parse_mode=HTML`. Tekst sformatowany pod Telegram, który
    trafi tu wspólną ścieżką `send_text`, pokazałby na ekranie blokady
    dosłowne `<b>` i `<code>` (dokładnie to był zgłoszony błąd).

    To SIATKA BEZPIECZEŃSTWA, nie sposób budowania treści: każde
    zdarzenie warte powiadomienia ma mieć własny builder w katalogu
    niżej. Ta funkcja tylko gwarantuje, że przyszłe `send_text(...)`
    z HTML-em nie wypłynie na telefon w surowej postaci.
    """
    return _HTML_TAG.sub("", text)


#: Nazwy kanałów w treści powiadomienia. `.capitalize()` dawało „Olx”
#: i nie miało co zrobić z `allegro_lokalnie`. Skrótów nie używamy -
#: „AL Lokalnie” wymagałoby domyślania się, co znaczy „AL”.
_CHANNEL_LABELS = {
    "allegro": "Allegro",
    "allegro_lokalnie": "AllegroLokalnie",
    "olx": "OLX",
    "amazon": "Amazon",
    "ebay": "eBay",
}


def _channel_label(code: str) -> str:
    """Czytelna nazwa kanału sprzedaży - z mapy, a nie z `.capitalize()`."""
    return _CHANNEL_LABELS.get(code.lower(), code.capitalize())


def _items(items: list[tuple[int, str]], limit: int = 52) -> str:
    """
    `50× Butelki PET 30 ml +2 poz.` - pierwsza pozycja z liczbą, reszta zwinięta.

    Powiadomienie ma powiedzieć ILE i CZEGO, a nie wyliczyć całe
    zamówienie - pełny spis czyta się w aplikacji, do której prowadzi
    kliknięcie. Skrót „poz.” zamiast „pozycje”, bo liczebnik wymagałby
    odmiany („1 pozycja”, „2 pozycje”, „5 pozycji”), a to wyskakuje na
    ekranie blokady kilka razy dziennie. Znak `×` (U+00D7) zamiast litery
    „x” - to mnożenie, nie litera.
    """
    if not items:
        return "brak danych"
    quantity, name = items[0]
    text = f"{quantity}× {_shorten(name, limit)}"
    if len(items) > 1:
        text += f" +{len(items) - 1} poz."
    return text


# --------------------------------------------------------------------------
# Katalog - sekcja 03. Czego tu nie ma, tego się nie wysyła.
# --------------------------------------------------------------------------


def new_order(
    *,
    marketplace: str,
    amount: Decimal,
    currency: str,
    products: list[tuple[int, str]],
    external_id: str,
    badge: int | None = None,
    silent: bool = False,
) -> PushPayload:
    """
    Nowe zamówienie - natychmiast. Ile, czego, za ile.

    Kanał siedzi w TREŚCI, nie w tytule: „Nowe zamówienie · Allegro”
    ucinało się na ekranie blokady już przy zwykłym Allegro, a przy
    AllegroLokalnie nie było czego czytać. Tytuł zmieści się teraz zawsze.

    Login kupującego zniknął stąd świadomie - z ekranu blokady i tak
    nic się z nim nie zrobi, a jest widoczny w aplikacji, do której
    prowadzi kliknięcie.
    """
    return PushPayload(
        title="Nowe zamówienie",
        body=f"{_channel_label(marketplace)} · {_items(products)} — {_money(amount, currency)}",
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
    breakdown = " · ".join(
        f"{_channel_label(channel)} {n}"
        for channel, n in sorted(per_channel.items(), key=lambda item: -item[1])
    )
    return PushPayload(
        title=f"{count} {_orders_word(count)}",
        body=f"{breakdown} — {_money(total_amount, currency)}",
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
        body=f"{name} — {stock} szt. (próg {min_stock})",
        thread="stock",
        url=f"/stock/{sku}",
        silent=silent,
        collapse_key=f"stock:{sku}",
    )


def new_dispute(
    *,
    buyer_login: str,
    reason: str | None,
    respond_by: datetime | None,
    issue_id: str,
    badge: int | None = None,
    silent: bool = False,
) -> PushPayload:
    """
    Kupujący rozpoczął dyskusję - natychmiast. Kto, o co i do kiedy
    trzeba odpowiedzieć.

    Termin pokazujemy jako KONKRETNĄ GODZINĘ, nie odliczanie („zostało
    6 godz."). Powiadomienie bywa czytane długo po dostarczeniu -
    odliczanie zdążyłoby się wtedy zestarzeć i skłamać, godzina nie.
    Gdy maila nie da się odczytać terminu, treść go po prostu pomija.

    Zastąpiło pozycję `unanswered_question`, która siedziała w katalogu
    bez żadnego producenta - nic w aplikacji jej nie wysyłało.
    """
    czesci = [buyer_login]
    if reason:
        czesci.append(f": {_shorten(reason, 40)}")
    if respond_by is not None:
        czesci.append(f" — odpowiedz do {respond_by.strftime('%d.%m, %H:%M')}")
    return PushPayload(
        title="Nowa dyskusja",
        body="".join(czesci),
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
    """
    Nowy zwrot do decyzji - natychmiast. Co wraca i dlaczego.

    Numer zwrotu zniknął z treści: to UUID, którego i tak nie da się
    przepisać z ekranu blokady, a kliknięcie prowadzi wprost do rekordu.
    """
    return PushPayload(
        title="Nowy zwrot",
        body=f"{_shorten(products_summary, 60)} — {reason}",
        thread="returns",
        url=f"/returns/{external_id}",
        silent=silent,
        badge=badge,
        collapse_key=f"return:{external_id}",
    )


def sync_failed(
    *,
    channel: str,
    retry_in_minutes: int,
    silent: bool = False,
) -> PushPayload:
    """
    Błąd synchronizacji - dopiero po DRUGIEJ nieudanej próbie.

    Treść trzyma się tonu z sekcji 7.3: co się stało i kiedy kolejna
    próba. Bez przeprosin.

    Zdanie o pozostałych kanałach zniknęło razem z parametrem
    `healthy_channels`: ORDLY dopuszcza jeden aktywny plugin naraz
    (patrz `Container.build_plugin`), więc brzmiało zawsze tak samo
    („Żaden inny kanał nie był aktywny”) i nic nie wnosiło.
    """
    return PushPayload(
        title=f"{_channel_label(channel)} nie odpowiada",
        body=f"Ponowna próba za {retry_in_minutes} minut",
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
        title=f"{wholesaler_name} potwierdziła",
        body=_shorten(items_summary, 70),
        thread="mail",
        url="/mailbox",
        silent=True,
        actions=[_ACTION_SHOW],
    )


#: Tytuły zdarzeń z Allegro Lokalnie. Klucze pochodzą z
#: `domain/entities/allegro_lokalnie_event.py`. Nazwa kanału NIE jest tu
#: doklejana - „Nowe zamówienie · Allegro Lokalnie” ucinało się na
#: ekranie blokady w połowie słowa. Kanał idzie do treści, tak samo jak
#: w `new_order`.
_ALLEGRO_LOKALNIE_TITLES = {
    "new_order": "Nowe zamówienie",
    "order_status": "Zmiana zamówienia",
    "new_message": "Nowa wiadomość",
    "interest": "Pytanie o ogłoszenie",
    "unknown": "AllegroLokalnie",
}


def allegro_lokalnie_event(
    *,
    event_type: str,
    listing_title: str,
    quantity: int | None,
    amount: Decimal | None,
    message_id: str,
    silent: bool = False,
) -> PushPayload:
    """
    Zdarzenie z Allegro Lokalnie - jedyne źródło wiedzy o tamtej sprzedaży.

    Treść trzyma ten sam układ co `new_order` (kanał w treści, potem ile,
    czego i za ile), bo dla użytkownika to jest po prostu sprzedaż -
    tylko z serwisu, którym z ORDLY nie da się sterować.

    Powiadomienie nie prowadzi do rekordu zamówienia (Allegro Lokalnie
    nie ma API, więc takiego rekordu w ORDLY nie ma), tylko do maila,
    z którego zdarzenie zostało odczytane - tam jest pełna treść
    i klikalny link do ogłoszenia.

    `event_type` spoza katalogu (nierozpoznany szablon maila) dostaje
    neutralny tytuł zamiast zniknąć - lepiej powiadomić "coś przyszło,
    sprawdź" niż przemilczeć sprzedaż.
    """
    title = _ALLEGRO_LOKALNIE_TITLES.get(event_type, _ALLEGRO_LOKALNIE_TITLES["unknown"])
    kanal = _channel_label("allegro_lokalnie")
    pozycja = _items([(quantity, listing_title)]) if quantity else _shorten(listing_title, 62)
    body = f"{kanal} · {pozycja}" if title != kanal else pozycja
    if amount is not None:
        body = f"{body} — {_money(amount)}"
    return PushPayload(
        title=title,
        body=body,
        thread="mail",
        url=f"/mailbox/{quote(message_id, safe='')}",
        silent=silent,
        collapse_key=f"al:{message_id}",
    )


def unmatched_products(
    *,
    reference: str,
    product_names: list[str],
    silent: bool = False,
) -> PushPayload:
    """
    Sprzedaż bez powiązania z magazynem - stan się nie zmienił.

    Zdarzenie miało dotąd tylko wariant telegramowy i szło na telefon
    wspólną ścieżką `send_text`, przez co na ekranie blokady lądowały
    dosłowne `<b>` i `<code>` (zgłoszony błąd). Teraz ma własną pozycję
    w katalogu: tytuł mówi, CO się stało, treść - której pozycji to
    dotyczy, a kliknięcie prowadzi do zamówienia, nie do ustawień.

    Numer zamówienia nie wchodzi do treści - pełny UUID zająłby całą
    linię, a i tak nie da się go przepisać z ekranu blokady.
    """
    if not product_names:
        opis = "brak danych"
    else:
        extra = f" +{len(product_names) - 1} poz." if len(product_names) > 1 else ""
        opis = f"{_shorten(product_names[0], 52)}{extra}"
    return PushPayload(
        title="Sprzedaż poza magazynem",
        body=f"{opis} — stan bez zmian",
        thread="stock",
        url=f"/orders/{reference}",
        silent=silent,
        collapse_key=f"unmatched:{reference}",
    )


def pending_packing(
    *,
    count: int,
    oldest_since: str,
    badge: int | None = None,
    silent: bool = False,
) -> PushPayload:
    """
    Zaległe pakowanie - raz dziennie o 9:00. Od kiedy czeka najstarsze.

    Tytuł bez słowa „zamówienia”: „3 zamówienia do spakowania” ucinało
    się na ekranie blokady, a liczba i tak mówi wszystko.
    """
    return PushPayload(
        title=f"{count} do spakowania",
        body=f"Najstarsze czeka od {oldest_since}",
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
