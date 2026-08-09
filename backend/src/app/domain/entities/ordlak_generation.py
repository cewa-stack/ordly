"""Encja domenowa: pojedyncza generacja oferty Allegro przez Ordlaka."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# Stany produktu obsługiwane przez formularz Ordlaka. Trzymane tutaj, a nie
# w API, bo prompt do modelu i walidacja korzystają z tej samej listy.
ORDLAK_CONDITIONS: dict[str, str] = {
    "new": "nowy, nieużywany",
    "very_good": "bardzo dobry, ślady użytkowania praktycznie niewidoczne",
    "good": "dobry, widoczne ślady normalnego użytkowania",
    "damaged": "uszkodzony, wymaga naprawy lub ma wadę",
}


@dataclass(frozen=True, slots=True)
class PriceBreakdown:
    """
    Rozbicie kalkulacji ceny - liczone deterministycznie, nigdy przez AI.

    Istnieje jako osobna encja (a nie luźne pola), żeby dokładnie ta sama
    struktura wracała z endpointu generowania i z historii - UI renderuje
    kartę ceny jednym komponentem.
    """

    purchase_cost: float
    inbound_shipping_cost: float
    buyer_shipping_cost: float
    commission_percent: float
    target_margin_percent: float
    commission_amount: float
    suggested_price: float


@dataclass(frozen=True, slots=True)
class OrdlakGeneration:
    """
    Zapisana generacja oferty.

    Zdjęcia NIE są częścią encji - trafiają do promptu i są odrzucane po
    odpowiedzi modelu (patrz `bot.md`, sekcja 3). Historia trzyma tylko
    `photo_count`, żeby dało się powiedzieć "ta oferta powstała z 2 zdjęć".
    """

    id: int | None
    created_at: datetime

    user_note: str
    condition: str
    purchase_cost: float
    inbound_shipping_cost: float
    buyer_shipping_cost: float
    commission_percent: float
    target_margin_percent: float
    photo_count: int

    generated_title: str
    generated_description_html: str
    ai_condition_notes: str | None

    suggested_price: float

    final_title: str | None = None
    final_description_html: str | None = None

    @property
    def title(self) -> str:
        """Tytuł do pokazania: wersja poprawiona przez użytkownika, jeśli istnieje."""
        return self.final_title or self.generated_title

    @property
    def description_html(self) -> str:
        """Opis do pokazania: wersja poprawiona przez użytkownika, jeśli istnieje."""
        return self.final_description_html or self.generated_description_html
