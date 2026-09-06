"""
Ordlak - asystent ORDLY. Czat, który odpowiada na pytania o stan sklepu.

Model nie tworzy tu żadnych treści od siebie, tylko RAPORTUJE: ile się
sprzedało, co ma niski stan, co się zbliża w kalendarzu sprzedażowym.

Zasada naczelna: **liczby pochodzą z bazy, nie z modelu**. Każda konkretna
wartość, którą asystent poda, musi przejść przez narzędzie zdefiniowane
w tym pliku - system prompt zabrania zgadywania, a narzędzia są jedynym
oknem na dane. Dzięki temu raport da się zweryfikować, klikając w ten sam
ekran w aplikacji.

Rozmowa jest bezstanowa po stronie serwera: aplikacja przysyła całą
historię przy każdym pytaniu. Jeden użytkownik, krótkie wątki - baza
rozmów byłaby tu kosztem bez zysku.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from loguru import logger

from app.core.config import OrdlakSettings
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.order import Order
from app.domain.entities.ordlak_conversation import (
    OrdlakConversation,
    title_from_question,
)
from app.domain.interfaces.order_repository import OrderRepository
from app.domain.interfaces.ordlak_conversation_repository import (
    OrdlakConversationRepository,
)
from app.domain.sales_calendar import upcoming_events
from app.services.dashboard_service import DashboardService
from app.services.health_service import HealthService
from app.services.inventory_service import InventoryService
from app.services.issues_service import IssuesService
from app.services.mailbox_service import MailboxService
from app.services.returns_service import ReturnsService
from app.services.search_service import SearchService
from app.utils.time import local_now, utc_now

# Klient Anthropic jest typowany jako `Any`, bo `AsyncAnthropic` importuje
# się dopiero w `build_anthropic_client` (brak paczki nie może wywalić
# startu aplikacji, gdy Ordlak nie jest używany), a testy podstawiają tu
# własnego sobowtóra. Protokół strukturalny nie zadziałałby: `messages.create`
# w SDK ma dziesiątki nazwanych parametrów, więc żaden zwięzły podpis go
# nie pokryje.
ClientFactory = Callable[[], Any]

#: Ile razy model może poprosić o dane, zanim musi odpowiedzieć.
#: Realne pytanie ("ile sprzedałem i co domówić?") mieści się w 2-3
#: narzędziach; limit chroni przed pętlą, w której model w kółko pyta
#: o to samo i pali tokeny.
MAX_TOOL_ROUNDS = 6

#: Odpowiedź asystenta to kilka akapitów albo lista - nie opis oferty.
_ANTHROPIC_MAX_TOKENS = 4096

#: Ile ostatnich wypowiedzi zapisanego wątku leci do modelu. Dłuższa
#: historia kosztowałaby przy KAŻDEJ kolejnej odpowiedzi, a raport i tak
#: dotyczy ostatniego pytania.
MAX_HISTORY_TURNS = 20

#: Ile ostatnich zamówień wchodzi do rozbicia na kanały i topkę produktów.
#: Liczby zbiorcze (ile sztuk, za ile) idą z agregatów repozytorium i są
#: dokładne; rozbicie liczymy z tej próbki i mówimy o tym wprost.
_BREAKDOWN_SAMPLE = 400

_PERIOD_LABEL: dict[str, str] = {
    "dzis": "dzisiaj",
    "wczoraj": "wczoraj",
    "7dni": "ostatnie 7 dni (z dzisiejszym)",
    "30dni": "ostatnie 30 dni (z dzisiejszym)",
    "biezacy_miesiac": "bieżący miesiąc",
}


class OrdlakError(Exception):
    """Błąd Ordlaka gotowy do pokazania użytkownikowi (czytelny po polsku)."""


class OrdlakNotConfiguredError(OrdlakError):
    """Brak ANTHROPIC_API_KEY - moduł jest wyłączony do czasu konfiguracji."""


class OrdlakConversationNotFoundError(OrdlakError):
    """Wskazany wątek rozmowy nie istnieje (np. usunięty w innym oknie)."""


def build_anthropic_client(
    settings: OrdlakSettings, client_factory: ClientFactory | None = None
) -> Any:
    """
    Zwraca klienta Anthropic albo sobowtóra podstawionego przez testy.

    Raises:
        OrdlakNotConfiguredError: Brak ANTHROPIC_API_KEY w `.env` na Pi.
    """
    if client_factory is not None:
        return client_factory()
    if not settings.enabled:
        raise OrdlakNotConfiguredError(
            "Ordlak nie ma klucza API. Uzupełnij ANTHROPIC_API_KEY w pliku "
            "~/ordly/backend/.env na Pi i zrestartuj usługę: "
            "sudo systemctl restart ordly. To osobny klucz z "
            "console.anthropic.com, nie subskrypcja Claude Pro."
        )
    # Import lokalny: brak paczki `anthropic` nie może wywalić startu
    # całej aplikacji, gdy Ordlak nie jest w ogóle używany.
    from anthropic import AsyncAnthropic

    return AsyncAnthropic(api_key=settings.api_key.get_secret_value())


def describe_api_error(exc: Exception) -> str:
    """Zamienia wyjątek SDK Anthropic na komunikat zrozumiały dla użytkownika."""
    status = getattr(exc, "status_code", None)
    if status == 401:
        return (
            "Anthropic odrzucił klucz API (401). Sprawdź ANTHROPIC_API_KEY "
            "w ~/ordly/backend/.env na Pi."
        )
    if status == 429:
        return "Przekroczony limit zapytań do Anthropic (429). Spróbuj za chwilę."
    if status == 400:
        return f"Anthropic odrzucił zapytanie (400): {exc}"
    if isinstance(status, int) and status >= 500:
        return f"Anthropic ma awarię ({status}). Spróbuj za chwilę."
    return f"Nie udało się połączyć z Anthropic API: {exc}"


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """Jedna wypowiedź w rozmowie - przysyłana przez aplikację."""

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    """Odpowiedź asystenta plus ślad po tym, z czego ją zbudował."""

    reply: str
    used_tools: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChatResult(AssistantAnswer):
    """Odpowiedź razem z wątkiem, do którego trafiła."""

    conversation_id: int


TOOLS: list[dict[str, Any]] = [
    {
        "name": "podsumowanie_sprzedazy",
        "description": (
            "Sprzedaz w wybranym okresie: liczba zamowien, przychod, rozbicie "
            "na kanaly (Allegro / Allegro Lokalnie / OLX), najczesciej "
            "sprzedawane produkty i przychod dzien po dniu. Uzyj do kazdego "
            "pytania w stylu 'ile sie sprzedalo', 'jak poszlo w tym tygodniu'."
        ),
        "input_schema": {
            "type": "object",
            "required": ["okres"],
            "properties": {
                "okres": {
                    "type": "string",
                    "enum": ["dzis", "wczoraj", "7dni", "30dni", "biezacy_miesiac"],
                    "description": "Zakres czasu, za ktory liczymy sprzedaz.",
                }
            },
        },
    },
    {
        "name": "niskie_stany",
        "description": (
            "Produkty, ktorych stan spadl do progu minimalnego albo ponizej - "
            "czyli lista zakupowa do hurtowni. Uzyj przy 'co ma niski stan', "
            "'co domowic', 'czego brakuje'."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "magazyn",
        "description": (
            "Stan magazynowy. Bez argumentu 'szukaj' zwraca przeglad calego "
            "magazynu, z argumentem - tylko pozycje pasujace do frazy w nazwie "
            "lub SKU. Uzyj przy pytaniu o konkretny produkt albo o to, ile "
            "czegos zostalo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "szukaj": {
                    "type": "string",
                    "description": "Fragment nazwy albo SKU produktu.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Ile pozycji zwrocic (1-60, domyslnie 25).",
                },
            },
        },
    },
    {
        "name": "prognoza_zapasow",
        "description": (
            "Na ile dni starczy zapasu przy obecnym tempie sprzedazy, wartosc "
            "magazynu oraz produkty, ktore nie sprzedaly sie ani razu w oknie "
            "prognozy. Uzyj przy 'co sie skonczy', 'na kiedy zamowic'."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ostatnie_zamowienia",
        "description": (
            "Lista ostatnich zamowien: numer, kanal, kupujacy, kwota, status "
            "realizacji i produkty. Z 'tylko_niewyslane' pokazuje tylko te, "
            "ktore czekaja na wysylke."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Ile zamowien zwrocic (1-30, domyslnie 10).",
                },
                "tylko_niewyslane": {
                    "type": "boolean",
                    "description": "True = tylko zamowienia czekajace na wysylke.",
                },
            },
        },
    },
    {
        "name": "zwroty",
        "description": "Ostatnie zwroty klientow: numer zwrotu, zamowienie, status, produkty.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Ile zwrotow zwrocic (1-30, domyslnie 10).",
                }
            },
        },
    },
    {
        "name": "kalendarz_sprzedazowy",
        "description": (
            "Nadchodzace dni sprzedazowe i swieta w Polsce: data szczytu, ile "
            "dni zostalo, kiedy najpozniej wystawic oferty i co sie wtedy "
            "sprzedaje. Uzyj przy 'jakie dni sprzedazowe sie zblizaja', 'na co "
            "sie przygotowac', 'kiedy wystawic oferty'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dni_do_przodu": {
                    "type": "integer",
                    "description": "Horyzont w dniach (7-365, domyslnie 60).",
                }
            },
        },
    },
    {
        "name": "szukaj",
        "description": (
            "Szuka zamowien po dowolnym fragmencie: numerze zamowienia, "
            "loginie kupujacego albo nazwie produktu. Uzyj przy 'co kupil X', "
            "'znajdz zamowienie z...', 'ile razy wracal ten klient'."
        ),
        "input_schema": {
            "type": "object",
            "required": ["fraza"],
            "properties": {
                "fraza": {
                    "type": "string",
                    "description": "Numer zamowienia, login kupujacego albo fragment nazwy produktu.",
                }
            },
        },
    },
    {
        "name": "dyskusje",
        "description": (
            "Lista dyskusji i reklamacji z Allegro (na zywo, nie z bazy): "
            "numer, typ, status, zamowienie, kupujacy, temat, liczba "
            "wiadomosci. Uzyj przy 'co mam do odpisania', 'jakie sa "
            "reklamacje'."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "watek_dyskusji",
        "description": (
            "Cala rozmowa jednej dyskusji lub reklamacji, od najstarszej "
            "wiadomosci. Uzyj ZAWSZE przed zaproponowaniem odpowiedzi - bez "
            "przeczytania watku nie wiesz, o co pyta kupujacy."
        ),
        "input_schema": {
            "type": "object",
            "required": ["id_dyskusji"],
            "properties": {
                "id_dyskusji": {
                    "type": "string",
                    "description": "Numer dyskusji z narzedzia 'dyskusje'.",
                }
            },
        },
    },
    {
        "name": "poczta",
        "description": (
            "Maile od marketplace wykryte w skrzynce: nadawca, temat, data, "
            "zrodlo, poczatek tresci. Uzyj przy 'co przyszlo', 'czy cos "
            "wymaga reakcji', 'jakie mam nieprzeczytane'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zrodlo": {
                    "type": "string",
                    "enum": ["allegro", "allegro_lokalnie", "olx", "other"],
                    "description": "Filtr kanalu. Pomin, zeby zobaczyc wszystko.",
                },
                "tylko_nieprzeczytane": {
                    "type": "boolean",
                    "description": "True = tylko maile nieoznaczone jako przeczytane.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Ile maili zwrocic (1-30, domyslnie 15).",
                },
            },
        },
    },
    {
        "name": "kalkulator_ceny",
        "description": (
            "Liczy cene sprzedazy przy zadanej marzy. Wzor uwzglednia regule "
            "Allegro: prowizja naliczana jest od SUMY ceny i kosztu wysylki "
            "pobranego od kupujacego, nie od samej ceny. Uzyj przy 'za ile "
            "wystawic', 'ile zarobie przy tej cenie'. NIGDY nie licz ceny "
            "w glowie - to narzedzie jest jedynym zrodlem tej liczby."
        ),
        "input_schema": {
            "type": "object",
            "required": ["koszt_zakupu", "prowizja_procent", "marza_procent"],
            "properties": {
                "koszt_zakupu": {
                    "type": "number",
                    "description": "Ile kosztowal towar (zl).",
                },
                "prowizja_procent": {
                    "type": "number",
                    "description": "Prowizja Allegro w procentach, np. 10.",
                },
                "marza_procent": {
                    "type": "number",
                    "description": "Docelowa marza w procentach, np. 30.",
                },
                "koszt_sprowadzenia": {
                    "type": "number",
                    "description": "Koszt sprowadzenia towaru do siebie (zl), domyslnie 0.",
                },
                "koszt_wysylki_do_kupujacego": {
                    "type": "number",
                    "description": (
                        "Koszt wysylki, ktory zaplaci kupujacy (zl), domyslnie 0. "
                        "Wchodzi do podstawy prowizji."
                    ),
                },
            },
        },
    },
    {
        "name": "stan_systemu",
        "description": (
            "Kondycja samego ORDLY: kiedy byla ostatnia synchronizacja, czy "
            "polaczenie z Allegro dziala, ile zamowien czeka na wysylke, ile "
            "pozycji jest ponizej progu. Uzyj przy 'jak leci', 'co dzis do "
            "zrobienia', 'czy wszystko dziala'."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _system_prompt(today: date) -> str:
    """System prompt z wstrzykniętą dzisiejszą datą (model jej nie zna)."""
    return f"""\
Jesteś Ordlakiem - asystentem wbudowanym w ORDLY, aplikację do prowadzenia
sprzedaży na Allegro, Allegro Lokalnie i OLX. Pracujesz dla jednej osoby:
właściciela tego sklepu. Mówisz po polsku, na "ty", zwięźle i konkretnie.

Dzisiaj jest {today.isoformat()}.

ZASADA NACZELNA: każda liczba, nazwa produktu, kwota i data w Twojej
odpowiedzi musi pochodzić z narzędzia. Nigdy nie zgaduj, nie szacuj
"mniej więcej" i nie powołuj się na pamięć z wcześniejszych rozmów.
Jeśli narzędzie zwróci pusto, powiedz wprost, że danych nie ma - to jest
poprawna odpowiedź, a wymyślona liczba nie.

JAK ODPOWIADAĆ:
- Zacznij od odpowiedzi, nie od opisu, co zaraz zrobisz.
- Liczby podawaj w złotówkach z groszami (np. 1 249,90 zł) i ze sztukami.
- Listy - maksymalnie 5-8 pozycji, najważniejsze na górze. Resztę streść
  jednym zdaniem ("i 12 innych pozycji").
- Nie używaj tabel ani HTML - czysty tekst, myślniki na listy.
- Gdy widzisz w danych coś niepokojącego (produkt schodzi za 3 dni,
  zamówienie czeka na wysyłkę drugi dzień) - powiedz o tym sam, bez pytania.
- Gdy pytanie jest szersze niż jedno narzędzie ("jak leci?"), zbierz dane
  z kilku i podaj jeden spójny obraz.
- Wyniki narzędzi przychodzą bez polskich znaków ("Zamowienia", "ponizej
  progu") - to zapis techniczny. Ty pisz normalną polszczyzną z ogonkami,
  a nazwy produktów przepisuj dokładnie tak, jak zwróciło narzędzie.

ODPOWIEDZI NA DYSKUSJE I REKLAMACJE: gdy użytkownik prosi o odpowiedź dla
kupującego, NAJPIERW przeczytaj wątek narzędziem `watek_dyskusji`, potem
napisz gotowy tekst do wysłania - uprzejmy, rzeczowy, po polsku, bez
obiecywania niczego, czego nie widzisz w danych (terminów, zwrotów kosztów,
rabatów). Sam tekst odpowiedzi podaj jako ostatni akapit, bez cudzysłowów
i bez komentarza po nim, żeby dało się go skopiować jednym ruchem.

CENA: nigdy nie licz jej w pamięci. Do każdego pytania "za ile wystawić"
użyj narzędzia `kalkulator_ceny` - ono zna regułę Allegro, że prowizja
naliczana jest też od kosztu wysyłki.

CZEGO NIE ROBISZ: nie wysyłasz maili, nie odpowiadasz za użytkownika
w dyskusjach, nie zmieniasz stanów magazynowych i nie zmieniasz niczego
w aplikacji. Jesteś od patrzenia, liczenia i pisania propozycji. Gdy
użytkownik prosi o akcję, powiedz, na którym ekranie ORDLY ją wykona
(Magazyn, Hurtownie, Zamówienia, Dyskusje, Poczta).
"""


def _money(value: Decimal | float | int | None) -> float:
    """Kwota jako zwykły float - JSON narzędzia nie zna Decimala."""
    if value is None:
        return 0.0
    return round(float(value), 2)


@dataclass(frozen=True, slots=True)
class PriceBreakdown:
    """Rozbicie kalkulacji ceny - wynik `calculate_price`."""

    purchase_cost: float
    inbound_shipping_cost: float
    buyer_shipping_cost: float
    commission_percent: float
    target_margin_percent: float
    commission_amount: float
    margin_amount: float
    suggested_price: float


def calculate_price(
    purchase_cost: float,
    commission_percent: float,
    target_margin_percent: float,
    inbound_shipping_cost: float = 0.0,
    buyer_shipping_cost: float = 0.0,
) -> PriceBreakdown:
    """
    Liczy sugerowaną cenę sprzedaży przy zadanej marży.

    **Cena liczy się TUTAJ, w Pythonie, nigdy w modelu.** To jedyny
    wyjątek od reguły "asystent tylko czyta bazę": liczba, której nie ma
    w żadnej tabeli, ale która musi być powtarzalna i audytowalna.

    Allegro nalicza prowizję od sumy ceny I kosztu wysyłki pobranego od
    kupującego, dlatego `buyer_shipping_cost` wchodzi do licznika przez
    prowizję, a nie jako zwykły koszt własny:

        P = (zakup + sprowadzenie + prowizja% * wysyłka_do_kupującego)
            / (1 - prowizja% - marża%)

    Raises:
        OrdlakError: Gdy prowizja + marża >= 100% (mianownik <= 0) albo gdy
            któraś z kwot jest ujemna - bez tego wzór zwracałby cenę ujemną
            albo dzielenie przez zero.
    """
    for label, value in (
        ("Koszt zakupu", purchase_cost),
        ("Koszt sprowadzenia towaru", inbound_shipping_cost),
        ("Koszt wysyłki do kupującego", buyer_shipping_cost),
        ("Prowizja", commission_percent),
        ("Marża", target_margin_percent),
    ):
        if value < 0:
            raise OrdlakError(f"{label} nie może być ujemna.")

    denominator = 1 - commission_percent / 100 - target_margin_percent / 100
    if denominator <= 0:
        raise OrdlakError(
            "Prowizja i marża razem muszą być mniejsze niż 100% "
            f"(podano {commission_percent:g}% + {target_margin_percent:g}%). "
            "Przy takich wartościach nie da się wyliczyć ceny."
        )

    numerator = (
        purchase_cost + inbound_shipping_cost + commission_percent / 100 * buyer_shipping_cost
    )
    suggested_price = round(numerator / denominator, 2)

    return PriceBreakdown(
        purchase_cost=round(purchase_cost, 2),
        inbound_shipping_cost=round(inbound_shipping_cost, 2),
        buyer_shipping_cost=round(buyer_shipping_cost, 2),
        commission_percent=commission_percent,
        target_margin_percent=target_margin_percent,
        commission_amount=round(
            commission_percent / 100 * (suggested_price + buyer_shipping_cost), 2
        ),
        margin_amount=round(target_margin_percent / 100 * suggested_price, 2),
        suggested_price=suggested_price,
    )


class OrdlakAssistantService:
    """
    Prowadzi rozmowę z modelem, wykonując po drodze zapytania o dane.

    Serwisy przychodzą przez konstruktor (nie przez kontener), żeby testy
    mogły podstawić fake'i - ta sama konwencja co `OrdlakService`.
    """

    def __init__(
        self,
        settings: OrdlakSettings,
        order_repository: OrderRepository,
        inventory_service: InventoryService,
        returns_service: ReturnsService,
        dashboard_service: DashboardService,
        health_service: HealthService,
        search_service: SearchService,
        issues_service: IssuesService,
        mailbox_service: MailboxService,
        conversation_repository: OrdlakConversationRepository,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._orders = order_repository
        self._inventory = inventory_service
        self._returns = returns_service
        self._dashboard = dashboard_service
        self._health = health_service
        self._search = search_service
        self._issues = issues_service
        self._mailbox = mailbox_service
        self._conversations = conversation_repository
        self._client_factory = client_factory

    async def ask(self, question: str, conversation_id: int | None = None) -> ChatResult:
        """
        Zadaje pytanie w wątku i zapisuje obie wypowiedzi.

        Wątek zakłada się dopiero przy pierwszym pytaniu - pusta rozmowa
        na liście byłaby śmieciem, którego użytkownik nie założył świadomie.

        Historia wysyłana do modelu jest przycięta do ostatnich
        `MAX_HISTORY_TURNS` wypowiedzi: bardzo długi wątek kosztowałby przy
        każdej odpowiedzi, a raport i tak dotyczy ostatniego pytania.

        Raises:
            OrdlakConversationNotFoundError: Podano `conversation_id`
                wątku, którego nie ma (np. usuniętego w innym oknie).
            OrdlakNotConfiguredError: Brak ANTHROPIC_API_KEY w `.env` na Pi.
            OrdlakError: Błąd API Anthropic albo model, który po
                `MAX_TOOL_ROUNDS` rundach dalej tylko pyta o dane.
        """
        question = question.strip()
        if not question:
            raise OrdlakError("Puste pytanie - nie ma na co odpowiedzieć.")

        history: list[ChatTurn] = []
        if conversation_id is None:
            conversation = await self._conversations.create(title_from_question(question))
        else:
            existing = await self._conversations.get(conversation_id)
            if existing is None:
                raise OrdlakConversationNotFoundError(
                    f"Rozmowa o numerze {conversation_id} nie istnieje."
                )
            conversation = existing
            history = [
                ChatTurn(role=message.role, content=message.content)
                for message in existing.messages[-MAX_HISTORY_TURNS:]
            ]

        thread_id = conversation.id
        assert thread_id is not None  # repozytorium zawsze nadaje id przy zapisie

        # Pytanie zapisujemy PRZED odpytaniem modelu: gdy Anthropic
        # odmówi albo padnie sieć, użytkownik ma wrócić do wątku i zobaczyć,
        # o co pytał, zamiast zastanawiać się, czy w ogóle wysłał.
        await self._conversations.append(thread_id, "user", question)

        answer = await self.answer([*history, ChatTurn(role="user", content=question)])
        await self._conversations.append(
            thread_id, "assistant", answer.reply, answer.used_tools
        )
        return ChatResult(
            reply=answer.reply, used_tools=answer.used_tools, conversation_id=thread_id
        )

    async def conversations(self, limit: int = 30) -> list[OrdlakConversation]:
        """Lista zapisanych wątków, od ostatnio używanego."""
        return await self._conversations.list_recent(limit=limit)

    async def conversation(self, conversation_id: int) -> OrdlakConversation | None:
        """Jeden wątek z pełną historią. `None` = nie ma takiego."""
        return await self._conversations.get(conversation_id)

    async def delete_conversation(self, conversation_id: int) -> bool:
        """Usuwa wątek. `False` = nie było czego usuwać."""
        return await self._conversations.delete(conversation_id)

    async def answer(self, messages: Sequence[ChatTurn]) -> AssistantAnswer:
        """
        Odpowiada na ostatnie pytanie, mając całą historię rozmowy.

        Raises:
            OrdlakNotConfiguredError: Brak ANTHROPIC_API_KEY w `.env` na Pi.
            OrdlakError: Błąd API Anthropic albo model, który po
                `MAX_TOOL_ROUNDS` rundach dalej tylko pyta o dane.
        """
        if not messages:
            raise OrdlakError("Pusta rozmowa - nie ma na co odpowiedzieć.")

        client = build_anthropic_client(self._settings, self._client_factory)
        conversation: list[dict[str, Any]] = [
            {"role": turn.role, "content": turn.content} for turn in messages
        ]
        used_tools: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self._call_model(client, conversation)
            blocks = list(getattr(response, "content", None) or [])
            tool_calls = [b for b in blocks if getattr(b, "type", None) == "tool_use"]

            if not tool_calls:
                return AssistantAnswer(
                    reply=self._extract_text(response), used_tools=tuple(used_tools)
                )

            conversation.append({"role": "assistant", "content": _blocks_to_params(blocks)})
            results = []
            for call in tool_calls:
                name = str(getattr(call, "name", ""))
                used_tools.append(name)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": getattr(call, "id", ""),
                        "content": await self._run_tool(
                            name, getattr(call, "input", None) or {}
                        ),
                    }
                )
            conversation.append({"role": "user", "content": results})

        raise OrdlakError(
            f"Ordlak nie doszedł do odpowiedzi w {MAX_TOOL_ROUNDS} podejściach. "
            "Zadaj pytanie węziej - np. o jeden okres albo jeden produkt."
        )

    # ------------------------------------------------------------------
    # Rozmowa z modelem
    # ------------------------------------------------------------------

    async def _call_model(self, client: Any, conversation: list[dict[str, Any]]) -> Any:
        try:
            return await client.messages.create(
                model=self._settings.model,
                max_tokens=_ANTHROPIC_MAX_TOKENS,
                system=_system_prompt(local_now().date()),
                messages=conversation,
                tools=TOOLS,
            )
        except Exception as exc:  # noqa: BLE001 - mapujemy wszystko na komunikat po polsku
            raise OrdlakError(describe_api_error(exc)) from exc

    @staticmethod
    def _extract_text(response: Any) -> str:
        """
        Skleja bloki tekstowe odpowiedzi.

        Pusty tekst przy `stop_reason == "max_tokens"` znaczy, że model
        zdążył tylko pomyśleć - komunikat mówi to wprost, zamiast oddać
        użytkownikowi pustą bańkę czatu.
        """
        parts = [
            str(getattr(block, "text", ""))
            for block in (getattr(response, "content", None) or [])
            if getattr(block, "type", None) == "text"
        ]
        text = "\n".join(part for part in parts if part).strip()
        if text:
            return text
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise OrdlakError(
                "Odpowiedź została ucięta na limicie długości. Zapytaj o węższy "
                "wycinek - np. o jeden okres zamiast o cały rok."
            )
        raise OrdlakError("Ordlak nie zwrócił odpowiedzi. Spróbuj zapytać ponownie.")

    async def _run_tool(self, name: str, payload: dict[str, Any]) -> str:
        """
        Wykonuje narzędzie i zwraca wynik jako tekst dla modelu.

        Błąd narzędzia wraca do modelu jako treść wyniku, a nie jako
        wyjątek - dzięki temu asystent może powiedzieć "nie udało się
        odczytać magazynu" zamiast wywalić cały czat.

        Wyniki narzędzi są pisane bez polskich znaków (jak cała reszta
        tekstu wysyłanego do modelu) - system prompt każe mu odpowiadać
        normalną polszczyzną, a jednolity zapis ułatwia asercje w testach.
        """
        try:
            handler = {
                "podsumowanie_sprzedazy": self._tool_sales_summary,
                "niskie_stany": self._tool_low_stock,
                "magazyn": self._tool_stock,
                "prognoza_zapasow": self._tool_forecast,
                "ostatnie_zamowienia": self._tool_orders,
                "zwroty": self._tool_returns,
                "kalendarz_sprzedazowy": self._tool_calendar,
                "szukaj": self._tool_search,
                "dyskusje": self._tool_issues,
                "watek_dyskusji": self._tool_issue_thread,
                "poczta": self._tool_mailbox,
                "kalkulator_ceny": self._tool_price,
                "stan_systemu": self._tool_system,
            }[name]
        except KeyError:
            logger.warning("Ordlak asystent: nieznane narzędzie {}", name)
            return f"BLAD: narzedzie '{name}' nie istnieje."

        try:
            return await handler(payload)
        except Exception as exc:  # noqa: BLE001 - model ma się dowiedzieć, że dane nie przyszły
            logger.exception("Ordlak asystent: narzędzie {} nie zadziałało", name)
            return f"BLAD odczytu danych ({name}): {exc}"

    # ------------------------------------------------------------------
    # Narzędzia
    # ------------------------------------------------------------------

    async def _tool_sales_summary(self, payload: dict[str, Any]) -> str:
        period = str(payload.get("okres", "dzis"))
        since, until = _period_bounds(period)

        orders_count = await self._orders.count_since(since)
        revenue = await self._orders.sum_amount_since(since)
        if until is not None:
            # Repozytorium liczy tylko "od", więc zamknięty przedział
            # (wczoraj) dostajemy przez odjęcie ogona.
            orders_count -= await self._orders.count_since(until)
            revenue -= await self._orders.sum_amount_since(until)

        by_day = await self._orders.sum_amount_by_day(since)
        sample = [
            order
            for order in await self._orders.get_recent(limit=_BREAKDOWN_SAMPLE)
            if order.order_date >= since and (until is None or order.order_date < until)
        ]

        lines = [
            f"Okres: {_PERIOD_LABEL.get(period, period)} "
            f"(od {since.date().isoformat()}"
            + (f" do {(until - timedelta(days=1)).date().isoformat()}" if until else "")
            + ")",
            f"Zamowienia: {orders_count}",
            f"Przychod: {_money(revenue)} zl",
        ]
        if orders_count:
            lines.append(f"Srednia wartosc zamowienia: {_money(revenue / orders_count)} zl")

        days = [
            f"{day}: {_money(amount)} zl"
            for day, amount in sorted(by_day.items())
            if until is None or day < until.date().isoformat()
        ]
        if days:
            lines.append("Przychod dzien po dniu: " + "; ".join(days))

        channels: dict[str, int] = {}
        for order in sample:
            channels[order.marketplace] = channels.get(order.marketplace, 0) + 1
        if channels:
            ranked = sorted(channels.items(), key=lambda pair: -pair[1])
            lines.append(
                "Kanaly (z "
                + str(len(sample))
                + " zamowien w tym okresie): "
                + "; ".join(f"{channel}: {count}" for channel, count in ranked)
            )

        top = _top_products(sample)
        if top:
            lines.append("Najczesciej sprzedawane w tym okresie:")
            lines.extend(
                f"- {name}: {quantity} szt., {_money(value)} zl" for name, quantity, value in top
            )
        else:
            lines.append("Brak sprzedanych pozycji w tym okresie.")
        return "\n".join(lines)

    async def _tool_low_stock(self, _payload: dict[str, Any]) -> str:
        items = await self._inventory.get_shopping_list()
        if not items:
            return "Zadna pozycja nie jest ponizej progu minimalnego."
        return "Pozycje ponizej progu:\n" + "\n".join(_stock_line(item) for item in items)

    async def _tool_stock(self, payload: dict[str, Any]) -> str:
        query = str(payload.get("szukaj") or "").strip().lower()
        limit = _clamp(payload.get("limit"), default=25, low=1, high=60)

        items = await self._inventory.get_stock_overview()
        if query:
            items = [
                item
                for item in items
                if query in item.name.lower() or query in item.sku.lower()
            ]
        if not items:
            return (
                f"Brak pozycji pasujacych do '{query}'."
                if query
                else "Magazyn jest pusty - nie ma zadnej pozycji."
            )

        head = items[:limit]
        lines = [_stock_line(item) for item in head]
        if len(items) > limit:
            lines.append(f"...oraz {len(items) - limit} dalszych pozycji.")
        return f"Pozycje magazynowe ({len(items)} pasujacych):\n" + "\n".join(lines)

    async def _tool_forecast(self, _payload: dict[str, Any]) -> str:
        report = await self._inventory.get_report()
        lines = [
            f"Pozycji w magazynie: {report.total_items}",
            f"Wartosc magazynu: {_money(report.total_stock_value)} zl",
            f"Ponizej progu: {len(report.low_stock_items)}",
        ]
        if report.forecasts:
            lines.append("Na ile dni starczy zapasu (najpilniejsze pierwsze):")
            lines.extend(
                f"- {f.name} ({f.sku}): {f.stock} szt., ok. {f.days_left} dni, "
                f"srednio {f.avg_daily_sales:.2f} szt./dzien"
                for f in report.forecasts[:10]
            )
        else:
            lines.append("Brak historii sprzedazy - nie ma z czego liczyc prognozy.")
        if report.items_without_sales:
            names = ", ".join(item.name for item in report.items_without_sales[:8])
            lines.append(
                f"Bez ani jednej sprzedazy w oknie prognozy ({len(report.items_without_sales)}): {names}"
            )
        return "\n".join(lines)

    async def _tool_orders(self, payload: dict[str, Any]) -> str:
        limit = _clamp(payload.get("limit"), default=10, low=1, high=30)
        if payload.get("tylko_niewyslane"):
            since = utc_now() - timedelta(days=90)
            orders = (await self._orders.get_unshipped_since(since))[:limit]
            header = f"Zamowienia czekajace na wysylke (z ostatnich 90 dni): {len(orders)}"
        else:
            orders = await self._orders.get_recent(limit=limit)
            header = f"Ostatnie zamowienia: {len(orders)}"

        if not orders:
            return header + "\nBrak zamowien do pokazania."
        return header + "\n" + "\n".join(_order_line(order) for order in orders)

    async def _tool_returns(self, payload: dict[str, Any]) -> str:
        limit = _clamp(payload.get("limit"), default=10, low=1, high=30)
        records = await self._returns.get_recent_returns(limit=limit)
        if not records:
            return "Brak zwrotow."
        return "Ostatnie zwroty:\n" + "\n".join(
            f"- {record.external_id} ({record.marketplace}) do zamowienia "
            f"{record.order_external_id}, status: {record.status}, "
            f"{record.return_date.date().isoformat()}, {record.products_summary}"
            for record in records
        )

    async def _tool_calendar(self, payload: dict[str, Any]) -> str:
        days_ahead = _clamp(payload.get("dni_do_przodu"), default=60, low=7, high=365)
        today = local_now().date()
        events = upcoming_events(today, days_ahead)
        if not events:
            return f"W najblizszych {days_ahead} dniach nie ma zadnego wydarzenia w kalendarzu."

        lines = [f"Dzis: {today.isoformat()}. Horyzont: {days_ahead} dni."]
        for event in events:
            definition = event.definition
            days_left = (event.peak - today).days
            kind = "okres sprzedazowy" if definition.category == "sprzedaz" else "swieto (dzien wolny)"
            when = "dzis" if days_left == 0 else f"za {days_left} dni"
            line = (
                f"- {definition.title} ({kind}): {event.peak.isoformat()}, {when}, "
                f"status: {event.status(today)}"
            )
            if definition.lead_days:
                line += (
                    f", oferty warto miec wystawione od {event.prep_start.isoformat()}"
                    f" (na {definition.lead_days} dni przed)"
                )
            lines.append(line + f". {definition.description}")
        return "\n".join(lines)

    async def _tool_search(self, payload: dict[str, Any]) -> str:
        query = str(payload.get("fraza") or "").strip()
        if not query:
            return "BLAD: podaj fraze do wyszukania."

        orders = await self._search.search_orders(query)
        if not orders:
            return f"Nic nie pasuje do '{query}'."

        head = orders[:20]
        lines = [_order_line(order) for order in head]
        if len(orders) > len(head):
            lines.append(f"...oraz {len(orders) - len(head)} dalszych zamowien.")
        total = sum(float(order.total_amount) for order in orders)
        header = (
            f"Znaleziono {len(orders)} zamowien dla '{query}', razem {_money(total)} zl:"
        )
        return header + "\n" + "\n".join(lines)

    async def _tool_issues(self, _payload: dict[str, Any]) -> str:
        issues = await self._issues.list_issues()
        if not issues:
            return "Brak dyskusji i reklamacji."
        return "Dyskusje i reklamacje:\n" + "\n".join(
            f"- {issue.external_id} ({issue.type}, status: {issue.status}) "
            f"do zamowienia {issue.order_external_id}, kupujacy {issue.buyer_login}, "
            f"otwarta {issue.opened_at.date().isoformat()}, "
            f"wiadomosci: {issue.messages_count}, "
            f"czat {'otwarty' if issue.chat_active else 'zamkniety'}"
            + (f", temat: {issue.subject}" if issue.subject else "")
            for issue in issues
        )

    async def _tool_issue_thread(self, payload: dict[str, Any]) -> str:
        issue_id = str(payload.get("id_dyskusji") or "").strip()
        if not issue_id:
            return "BLAD: podaj numer dyskusji."

        messages = await self._issues.get_thread(issue_id)
        if not messages:
            return f"Dyskusja {issue_id} nie ma zadnych wiadomosci."
        return f"Watek dyskusji {issue_id} (od najstarszej):\n" + "\n".join(
            f"[{message.created_at.strftime('%Y-%m-%d %H:%M')}] "
            f"{message.author_login} ({message.author_role}): {message.text}"
            for message in messages
        )

    async def _tool_mailbox(self, payload: dict[str, Any]) -> str:
        source = payload.get("zrodlo")
        limit = _clamp(payload.get("limit"), default=15, low=1, high=30)
        unread_only = bool(payload.get("tylko_nieprzeczytane"))

        status = await self._mailbox.get_status()
        if not status.configured:
            return (
                "Skrzynka IMAP nie jest skonfigurowana na Pi - nie ma zadnych maili "
                "do pokazania. To nie jest blad, tylko brak konfiguracji."
            )

        messages = await self._mailbox.list_messages(
            source=str(source) if source else None,
            unread_only=unread_only,
            limit=limit,
        )
        if not messages:
            filters = []
            if source:
                filters.append(f"zrodlo={source}")
            if unread_only:
                filters.append("tylko nieprzeczytane")
            suffix = f" (filtry: {', '.join(filters)})" if filters else ""
            return f"Brak maili{suffix}. W bazie jest lacznie {status.message_count}."

        header = f"Maile w skrzynce (lacznie w bazie: {status.message_count}):"
        return header + "\n" + "\n".join(
            f"- [{message.received_at.strftime('%Y-%m-%d %H:%M')}] "
            f"{'PRZECZYTANY' if message.is_read else 'NIEPRZECZYTANY'} "
            f"({message.source}) od {message.sender}: {message.subject}"
            + (f" | {message.body_preview}" if message.body_preview else "")
            for message in messages
        )

    async def _tool_price(self, payload: dict[str, Any]) -> str:
        try:
            breakdown = calculate_price(
                purchase_cost=float(payload["koszt_zakupu"]),
                commission_percent=float(payload["prowizja_procent"]),
                target_margin_percent=float(payload["marza_procent"]),
                inbound_shipping_cost=float(payload.get("koszt_sprowadzenia") or 0),
                buyer_shipping_cost=float(payload.get("koszt_wysylki_do_kupujacego") or 0),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return f"BLAD: zle dane do kalkulacji ceny ({exc})."
        except OrdlakError as exc:
            return f"BLAD: {exc}"

        return "\n".join(
            [
                f"Cena sugerowana: {breakdown.suggested_price} zl",
                f"Koszt zakupu: {breakdown.purchase_cost} zl",
                f"Koszt sprowadzenia: {breakdown.inbound_shipping_cost} zl",
                f"Wysylka od kupujacego: {breakdown.buyer_shipping_cost} zl",
                f"Prowizja {breakdown.commission_percent:g}% liczona od ceny + wysylki: "
                f"{breakdown.commission_amount} zl",
                f"Zakladana marza: {breakdown.target_margin_percent:g}% "
                f"({breakdown.margin_amount} zl)",
            ]
        )

    async def _tool_system(self, _payload: dict[str, Any]) -> str:
        health = await self._health.check()
        summary = await self._dashboard.get_summary()
        trend = (
            f"{summary.trend_percent:+.0f}% wzgledem sredniej z poprzednich dni"
            if summary.trend_percent is not None
            else "brak bazy do porownania trendu"
        )
        return "\n".join(
            [
                f"Ostatnia synchronizacja: {health.last_sync_human}",
                f"Baza danych dziala: {'tak' if health.database_ok else 'NIE'}",
                f"Polaczenie z Allegro: {'ok' if health.marketplace_connection_ok else 'BRAK'}",
                f"Aplikacja dziala od: {health.uptime_human}",
                f"Zamowienia dzis: {summary.orders_today}, przychod dzis: "
                f"{_money(summary.revenue_today)} zl ({trend})",
                f"Czeka na wysylke: {summary.orders_to_ship}",
                f"Ponizej progu w magazynie: {summary.low_stock_count}",
            ]
        )


# ----------------------------------------------------------------------
# Funkcje pomocnicze
# ----------------------------------------------------------------------


def _blocks_to_params(blocks: list[Any]) -> list[dict[str, Any]]:
    """
    Zamienia bloki odpowiedzi na słowniki, które można odesłać modelowi.

    Bloki `thinking` MUSZĄ wrócić w niezmienionej postaci razem z podpisem -
    model z włączonym myśleniem (domyślne w Sonnet 5) odrzuca turę
    z `tool_use`, w której ich zabrakło.
    """
    params: list[dict[str, Any]] = []
    for block in blocks:
        kind = getattr(block, "type", None)
        if kind == "text":
            params.append({"type": "text", "text": getattr(block, "text", "")})
        elif kind == "tool_use":
            params.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id", ""),
                    "name": getattr(block, "name", ""),
                    "input": getattr(block, "input", None) or {},
                }
            )
        elif kind == "thinking":
            params.append(
                {
                    "type": "thinking",
                    "thinking": getattr(block, "thinking", ""),
                    "signature": getattr(block, "signature", ""),
                }
            )
        elif kind == "redacted_thinking":
            params.append({"type": "redacted_thinking", "data": getattr(block, "data", "")})
    return params


def _period_bounds(period: str) -> tuple[datetime, datetime | None]:
    """
    Granice okresu jako (od, do) w naiwnym UTC. `do = None` znaczy "do teraz".

    Dni liczymy od północy UTC, tak samo jak `StatsService` i
    `DashboardService` - inaczej "dzisiaj" u asystenta znaczyłoby coś
    innego niż "dzisiaj" na ekranie Start.
    """
    now = utc_now()
    today_start = datetime(now.year, now.month, now.day)
    if period == "wczoraj":
        return today_start - timedelta(days=1), today_start
    if period == "7dni":
        return today_start - timedelta(days=6), None
    if period == "30dni":
        return today_start - timedelta(days=29), None
    if period == "biezacy_miesiac":
        return datetime(now.year, now.month, 1), None
    return today_start, None


def _clamp(value: Any, *, default: int, low: int, high: int) -> int:
    """Liczba z narzędzia sprowadzona do sensownego zakresu (model bywa hojny)."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _top_products(orders: list[Order]) -> list[tuple[str, int, float]]:
    """Najczęściej sprzedawane pozycje z próbki zamówień: (nazwa, sztuki, wartość)."""
    totals: dict[str, tuple[int, float]] = {}
    for order in orders:
        for product in order.products:
            quantity, value = totals.get(product.name, (0, 0.0))
            totals[product.name] = (
                quantity + product.quantity,
                value + float(product.total_price),
            )
    ranked = sorted(totals.items(), key=lambda pair: -pair[1][0])[:8]
    return [(name, quantity, value) for name, (quantity, value) in ranked]


def _stock_line(item: InventoryItem) -> str:
    parts = [f"- {item.name} ({item.sku}): {item.stock} szt."]
    if item.min_stock:
        parts.append(f"prog {item.min_stock}")
    if item.is_low_stock:
        parts.append("PONIZEJ PROGU")
    if item.sale_price is not None:
        parts.append(f"cena {_money(item.sale_price)} zl")
    if item.parent_sku:
        parts.append(f"podprodukt {item.parent_sku}")
    return ", ".join(parts)


def _order_line(order: Order) -> str:
    return (
        f"- {order.external_id} ({order.marketplace}), {order.buyer.login}, "
        f"{_money(order.total_amount)} {order.currency}, status: {order.status}, "
        f"realizacja: {order.fulfillment_status or 'nowe'}, "
        f"{order.order_date.date().isoformat()}, {order.products_summary}"
    )
