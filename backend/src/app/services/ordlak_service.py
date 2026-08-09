"""
Ordlak - generator ofert Allegro (AI + deterministyczna kalkulacja ceny).

Podział odpowiedzialności jest tu świadomy i twardy:
- **cena** liczy się w Pythonie, zawsze, wzorem z `bot_ordlak/bot.md` sekcja 5.
  Model AI nigdy jej nie podaje i nawet gdyby coś zasugerował w tekście,
  backend to ignoruje - kalkulacja ma być przewidywalna i audytowalna;
- **tytuł i opis** pochodzą z modelu, ale przechodzą przez walidację
  regulaminową (sekcja 6.1/6.2) zanim trafią do użytkownika.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.core.config import OrdlakSettings
from app.domain.entities.ordlak_generation import (
    ORDLAK_CONDITIONS,
    OrdlakGeneration,
    PriceBreakdown,
)
from app.domain.interfaces.ordlak_repository import OrdlakRepository
from app.utils.time import utc_now

# Limity regulaminowe Allegro (docs/allegro_regulamin/tytul-oferty.md).
TITLE_MIN_LENGTH = 12
TITLE_MAX_LENGTH = 75
TITLE_MIN_WORDS = 3
# Cel produktowy: wykorzystać maksimum miejsca na słowa kluczowe. Tytuł
# krótszy niż to jest regulaminowo legalny, ale marnuje miejsce pod SEO,
# więc backend ponawia raz zapytanie i - jeśli dalej krótko - sygnalizuje
# to flagą `title_below_target` zamiast po cichu oddać słabszy wynik.
TITLE_TARGET_LENGTH = 65

MAX_PHOTOS = 3
_ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}

_ANTHROPIC_MAX_TOKENS = 4096

_OFFER_TOOL = {
    "name": "submit_offer_draft",
    "description": "Zwraca gotowy szkic oferty Allegro: tytuł, opis HTML i ocenę stanu.",
    "input_schema": {
        "type": "object",
        "required": ["title", "description_html", "condition_notes"],
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "Tytul oferty Allegro. Cel: 74-75 znakow (maksymalne "
                    "wykorzystanie miejsca pod SEO), twardy limit 12-75 znakow "
                    "i minimum 3 slowa. Zawsze prawdziwe atrybuty produktu, "
                    "nigdy powtorzenia tego samego slowa."
                ),
            },
            "description_html": {
                "type": "string",
                "description": (
                    "Opis produktu jako prosty HTML (dozwolone: p, ul, li, "
                    "strong, br). Wylacznie cechy i stan produktu."
                ),
            },
            "condition_notes": {
                "type": "string",
                "description": (
                    "Krotka ocena stanu na podstawie zdjec. Pusty string, "
                    "jesli nie dolaczono zdjec."
                ),
            },
        },
    },
}

_SYSTEM_PROMPT = """\
Jesteś ekspertem od wystawiania ofert na Allegro. Tworzysz tytuł i opis
oferty zgodne z regulaminem Allegro i zoptymalizowane pod wyszukiwarkę Allegro.

ZASADY TYTUŁU (twarde):
- Długość 12-75 znaków ze spacjami, minimum 3 słowa.
- CELUJ W 74-75 ZNAKÓW. Wypełniaj limit kolejnymi PRAWDZIWYMI atrybutami
  produktu (marka, model, kolor, rozmiar, materiał, pojemność, przeznaczenie),
  aż zabraknie miejsca.
- Najważniejsze słowa kluczowe na początku.
- ZAKAZ: powtarzania tego samego słowa w celu wydłużenia tytułu, słów
  "tanio", "najtaniej", "okazja", "nowość", "promocja", "hit", "gratis",
  informacji o wysyłce, odbiorze osobistym, fakturach, loginie, mieście,
  numerów magazynowych, znaków ozdobnych (@ ! [ ]), CAPS LOCKA, nazw marek
  niezwiązanych z produktem.

ZASADY OPISU (twarde):
- Wyłącznie cechy i stan produktu.
- ZAKAZ: danych kontaktowych (telefon, e-mail, numer konta), zachęt do
  kontaktu lub zakupu poza Allegro, fraz reklamowych ("gratis", "tanio",
  "promocja", "hit", "prezent"), WZMIANEK O WYSYŁCE, DOSTAWIE, CZASIE
  REALIZACJI, KOSZTACH TRANSPORTU I ODBIORZE OSOBISTYM, linków, informacji
  o innych ofertach sprzedawcy, gwarancji i warunkach sprzedaży
  niezwiązanych z samym przedmiotem.
- Prosty HTML: <p>, <ul>, <li>, <strong>, <br>. Bez stylów i skryptów.

NIGDY nie podawaj ceny ani nie sugeruj kwoty - cenę wylicza system.
Odpowiadaj wyłącznie przez narzędzie submit_offer_draft.
"""

_RETRY_HINT = (
    "\n\nUWAGA: poprzedni tytuł był za krótki i marnował miejsce na słowa "
    "kluczowe. Dodaj więcej PRAWDZIWYCH, różnych atrybutów produktu, tak aby "
    "tytuł miał 74-75 znaków. Nie powtarzaj słów."
)


# Klient Anthropic jest typowany jako `Any`, bo `AsyncAnthropic` jest
# importowany dopiero w `_build_client` (brak paczki nie może wywalić startu
# aplikacji, gdy Ordlak nie jest używany), a testy podstawiają tu własnego
# sobowtóra. Protokół strukturalny nie zadziałałby: `messages.create` w SDK
# ma dziesiątki nazwanych parametrów, więc żaden zwięzły podpis go nie pokryje.
ClientFactory = Callable[[], Any]


class OrdlakError(Exception):
    """Błąd generowania oferty do pokazania użytkownikowi (czytelny po polsku)."""


class OrdlakNotConfiguredError(OrdlakError):
    """Brak klucza ANTHROPIC_API_KEY - moduł jest wyłączony do czasu konfiguracji."""


@dataclass(frozen=True, slots=True)
class OrdlakPhoto:
    """Zdjęcie przekazane do modelu. Żyje tylko w pamięci, nie trafia do bazy."""

    media_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class OrdlakDraft:
    """Wynik generacji zwracany do API (encja + flaga jakości tytułu)."""

    generation: OrdlakGeneration
    price_breakdown: PriceBreakdown
    title_below_target: bool


def calculate_price(
    purchase_cost: float,
    inbound_shipping_cost: float,
    buyer_shipping_cost: float,
    commission_percent: float,
    target_margin_percent: float,
) -> PriceBreakdown:
    """
    Liczy sugerowaną cenę sprzedaży (wzór z `bot.md` sekcja 5).

    Allegro nalicza prowizję od suma ceny I kosztu wysyłki pobranego od
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
    commission_amount = round(
        commission_percent / 100 * (suggested_price + buyer_shipping_cost), 2
    )

    return PriceBreakdown(
        purchase_cost=purchase_cost,
        inbound_shipping_cost=inbound_shipping_cost,
        buyer_shipping_cost=buyer_shipping_cost,
        commission_percent=commission_percent,
        target_margin_percent=target_margin_percent,
        commission_amount=commission_amount,
        suggested_price=suggested_price,
    )


def validate_title(title: str) -> None:
    """
    Sprawdza twarde limity regulaminowe tytułu.

    Raises:
        OrdlakError: Gdy tytuł wypada poza 12-75 znaków lub ma mniej niż
            3 słowa - taka oferta zostałaby odrzucona przez Allegro, więc
            lepiej pokazać błąd niż pozwolić skopiować zły tytuł.
    """
    length = len(title)
    if length < TITLE_MIN_LENGTH or length > TITLE_MAX_LENGTH:
        raise OrdlakError(
            f"Model zwrócił tytuł o długości {length} znaków, a Allegro wymaga "
            f"{TITLE_MIN_LENGTH}-{TITLE_MAX_LENGTH}. Spróbuj wygenerować ponownie."
        )
    if len(title.split()) < TITLE_MIN_WORDS:
        raise OrdlakError(
            f"Model zwrócił tytuł krótszy niż {TITLE_MIN_WORDS} słowa, a Allegro "
            "tego wymaga. Spróbuj wygenerować ponownie."
        )


class OrdlakService:
    """
    Generuje szkice ofert Allegro i zapisuje je w historii.

    Klient Anthropic jest wstrzykiwany przez `client_factory`, żeby testy
    mogły podstawić fake'a bez monkeypatchowania - ta sama konwencja co
    `MailboxService.watcher_factory` i `MailService.send_fn`.
    """

    def __init__(
        self,
        repository: OrdlakRepository,
        settings: OrdlakSettings,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._client_factory = client_factory

    async def generate(
        self,
        note: str,
        condition: str,
        purchase_cost: float,
        inbound_shipping_cost: float,
        buyer_shipping_cost: float,
        commission_percent: float,
        target_margin_percent: float,
        photos: Sequence[OrdlakPhoto] = (),
    ) -> OrdlakDraft:
        """
        Generuje ofertę: cena liczona lokalnie, tytuł i opis przez model AI.

        Raises:
            OrdlakNotConfiguredError: Brak ANTHROPIC_API_KEY w `.env` na Pi.
            OrdlakError: Błąd walidacji wejścia, limitu zdjęć albo odpowiedzi
                modelu - komunikat jest gotowy do pokazania użytkownikowi.
        """
        if not note.strip():
            raise OrdlakError("Notatka o produkcie jest wymagana.")
        if condition not in ORDLAK_CONDITIONS:
            raise OrdlakError(
                f"Nieznany stan produktu: '{condition}'. "
                f"Dozwolone: {', '.join(ORDLAK_CONDITIONS)}."
            )

        self._validate_photos(photos)

        # Cena najpierw - jeśli parametry są bezsensowne (prowizja + marża
        # >= 100%), nie ma po co płacić za zapytanie do modelu.
        breakdown = calculate_price(
            purchase_cost=purchase_cost,
            inbound_shipping_cost=inbound_shipping_cost,
            buyer_shipping_cost=buyer_shipping_cost,
            commission_percent=commission_percent,
            target_margin_percent=target_margin_percent,
        )

        draft = await self._ask_model(note=note, condition=condition, photos=photos)
        title, description_html, condition_notes = draft
        validate_title(title)

        title_below_target = len(title) < TITLE_TARGET_LENGTH

        generation = OrdlakGeneration(
            id=None,
            created_at=utc_now(),
            user_note=note.strip(),
            condition=condition,
            purchase_cost=purchase_cost,
            inbound_shipping_cost=inbound_shipping_cost,
            buyer_shipping_cost=buyer_shipping_cost,
            commission_percent=commission_percent,
            target_margin_percent=target_margin_percent,
            photo_count=len(photos),
            generated_title=title,
            generated_description_html=description_html,
            ai_condition_notes=condition_notes or None,
            suggested_price=breakdown.suggested_price,
        )
        saved = await self._repository.save(generation)

        return OrdlakDraft(
            generation=saved,
            price_breakdown=breakdown,
            title_below_target=title_below_target,
        )

    async def finalize(
        self, generation_id: int, final_title: str, final_description_html: str
    ) -> OrdlakGeneration | None:
        """Zapisuje ręcznie poprawiony tytuł/opis. None = nie ma takiej generacji."""
        return await self._repository.update_final_texts(
            generation_id, final_title, final_description_html
        )

    async def history(self, limit: int = 20, offset: int = 0) -> list[OrdlakGeneration]:
        """Zwraca historię generacji, najnowsze pierwsze."""
        return await self._repository.get_recent(limit=limit, offset=offset)

    async def get(self, generation_id: int) -> OrdlakGeneration | None:
        """Zwraca pojedynczą generację z historii."""
        return await self._repository.get_by_id(generation_id)

    # ------------------------------------------------------------------
    # Wewnętrzne
    # ------------------------------------------------------------------

    def _validate_photos(self, photos: Sequence[OrdlakPhoto]) -> None:
        if len(photos) > MAX_PHOTOS:
            raise OrdlakError(
                f"Maksymalnie {MAX_PHOTOS} zdjęcia na jedną generację "
                f"(przesłano {len(photos)})."
            )
        max_bytes = self._settings.max_photo_size_mb * 1024 * 1024
        for index, photo in enumerate(photos, start=1):
            if photo.media_type not in _ALLOWED_PHOTO_TYPES:
                raise OrdlakError(
                    f"Zdjęcie {index}: nieobsługiwany format '{photo.media_type}'. "
                    "Dozwolone: JPG, PNG, WEBP."
                )
            if len(photo.content) > max_bytes:
                size_mb = len(photo.content) / 1024 / 1024
                raise OrdlakError(
                    f"Zdjęcie {index} waży {size_mb:.1f} MB, limit to "
                    f"{self._settings.max_photo_size_mb} MB. Zmniejsz plik i spróbuj ponownie."
                )

    def _build_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        if not self._settings.enabled:
            raise OrdlakNotConfiguredError(
                "Ordlak nie ma klucza API. Uzupełnij ANTHROPIC_API_KEY w pliku "
                "~/ordly/backend/.env na Pi i zrestartuj usługę: "
                "sudo systemctl restart ordly. To osobny klucz z "
                "console.anthropic.com, nie subskrypcja Claude Pro."
            )
        # Import lokalny: brak paczki `anthropic` nie może wywalić startu
        # całej aplikacji, gdy Ordlak nie jest w ogóle używany.
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=self._settings.api_key.get_secret_value())

    def _build_user_content(
        self, note: str, condition: str, photos: Sequence[OrdlakPhoto]
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = []
        for photo in photos:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": photo.media_type,
                        "data": base64.standard_b64encode(photo.content).decode("ascii"),
                    },
                }
            )
        photo_hint = (
            "Oceń stan produktu na podstawie zdjęć powyżej."
            if photos
            else "Brak zdjęć - w polu condition_notes zwróć pusty string."
        )
        content.append(
            {
                "type": "text",
                "text": (
                    f"Notatka sprzedawcy o produkcie:\n{note.strip()}\n\n"
                    f"Stan produktu podany przez sprzedawcę: {ORDLAK_CONDITIONS[condition]}\n\n"
                    f"{photo_hint}\n\n"
                    "Przygotuj tytuł i opis oferty przez narzędzie submit_offer_draft."
                ),
            }
        )
        return content

    async def _ask_model(
        self, note: str, condition: str, photos: Sequence[OrdlakPhoto]
    ) -> tuple[str, str, str]:
        """
        Odpytuje model, w razie potrzeby ponawiając RAZ po zbyt krótki tytuł.

        Druga próba dostaje ten sam prompt plus dopisek o wydłużeniu tytułu.
        Jeśli i ona zwróci krótki tytuł, oddajemy ten wynik - lepszy krótszy
        trafny tytuł niż wymuszony bełkot (`bot.md` sekcja 6.1).
        """
        client = self._build_client()
        content = self._build_user_content(note, condition, photos)

        title, description_html, condition_notes = await self._call_anthropic(
            client, _SYSTEM_PROMPT, content
        )
        if len(title) >= TITLE_TARGET_LENGTH:
            return title, description_html, condition_notes

        logger.info(
            "Ordlak: tytuł ma {} znaków (cel {}), ponawiam raz",
            len(title),
            TITLE_TARGET_LENGTH,
        )
        try:
            retry = await self._call_anthropic(client, _SYSTEM_PROMPT + _RETRY_HINT, content)
        except OrdlakError:
            # Pierwsza odpowiedź jest poprawna, tylko krótsza niż cel -
            # nie ma powodu wywracać całej generacji przez nieudaną dogrywkę.
            logger.warning("Ordlak: ponowna próba nie powiodła się, zwracam pierwszy wynik")
            return title, description_html, condition_notes

        if len(retry[0]) > len(title):
            return retry
        return title, description_html, condition_notes

    async def _call_anthropic(
        self, client: Any, system_prompt: str, content: list[dict[str, Any]]
    ) -> tuple[str, str, str]:
        """Jedno wywołanie Messages API z wymuszonym narzędziem (structured output)."""
        try:
            response = await client.messages.create(
                model=self._settings.model,
                max_tokens=_ANTHROPIC_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": content}],
                tools=[_OFFER_TOOL],
                tool_choice={"type": "tool", "name": _OFFER_TOOL["name"]},
            )
        except Exception as exc:  # noqa: BLE001 - mapujemy wszystko na komunikat po polsku
            raise OrdlakError(self._describe_api_error(exc)) from exc

        return self._extract_tool_result(response)

    @staticmethod
    def _describe_api_error(exc: Exception) -> str:
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

    @staticmethod
    def _extract_tool_result(response: object) -> tuple[str, str, str]:
        """
        Wyciąga wynik z bloku `tool_use`.

        `tool_choice` wymusza użycie narzędzia, ale odpowiedź może zawierać
        też bloki tekstowe/thinking - dlatego szukamy bloku po typie zamiast
        zakładać, że wynik leży pod `content[0]`.
        """
        blocks = getattr(response, "content", None) or []
        for block in blocks:
            if getattr(block, "type", None) != "tool_use":
                continue
            payload = getattr(block, "input", None)
            if not isinstance(payload, dict):
                continue
            title = str(payload.get("title", "")).strip()
            description_html = str(payload.get("description_html", "")).strip()
            condition_notes = str(payload.get("condition_notes", "")).strip()
            if not title or not description_html:
                raise OrdlakError(
                    "Model zwrócił niekompletną ofertę (brak tytułu lub opisu). "
                    "Spróbuj wygenerować ponownie."
                )
            return title, description_html, condition_notes

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            raise OrdlakError(
                "Model odmówił wygenerowania oferty dla tej treści. "
                "Popraw notatkę o produkcie i spróbuj ponownie."
            )
        if stop_reason == "max_tokens":
            raise OrdlakError(
                "Odpowiedź modelu została ucięta (za długi opis). "
                "Skróć notatkę o produkcie i spróbuj ponownie."
            )
        raise OrdlakError("Model nie zwrócił oferty w oczekiwanym formacie. Spróbuj ponownie.")
