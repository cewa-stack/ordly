"""
Testy działań zapisujących Ordlaka.

Sprawdzamy trzy rzeczy, każdą osobno:

1. **Walidacja** (`build_action`) - że nie da się złożyć działania
   z brakującym albo bzdurnym parametrem. Ta sama funkcja chroni
   propozycję modelu i żądanie z aplikacji, więc wystarczy raz.
2. **Że model NICZEGO nie wykonuje** - propozycja ma wyjść z odpowiedzi
   jako `actions`, a serwisy zapisujące mają zostać nietknięte. To jest
   najważniejszy test w tym pliku: cały projekt tej funkcji stoi na tym,
   że zapis robi dopiero człowiek.
3. **Wykonanie** (`AssistantActionExecutor`) - że zatwierdzone działanie
   woła ten sam serwis, co zwykły endpoint aplikacji.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.entities.marketplace_offer import MarketplaceOffer
from app.services.assistant_actions import (
    MAX_QUANTITY,
    MAX_REPLY_CHARS,
    AssistantActionError,
    AssistantActionExecutor,
    build_action,
)
from app.services.issues_service import IssuesService
from app.services.offer_catalog_service import OfferCatalogService
from app.utils.time import utc_now
from tests.fakes.fake_marketplace_plugin import FakeMarketplacePlugin
from tests.fakes.fake_offer_catalog_repository import FakeOfferCatalogRepository

# ----------------------------------------------------------------------
# Walidacja
# ----------------------------------------------------------------------


class TestBuildAction:
    def test_nieznany_rodzaj_jest_odrzucany(self):
        with pytest.raises(AssistantActionError, match="Nieznane dzialanie"):
            build_action({"rodzaj": "usun_wszystko"})

    def test_brak_rodzaju_jest_odrzucany(self):
        with pytest.raises(AssistantActionError, match="Nieznane dzialanie"):
            build_action({})

    # ---- stan na półce ----

    def test_stan_sklada_sie_z_kompletu_parametrow(self):
        action = build_action(
            {
                "rodzaj": "ustaw_stan_oferty",
                "marketplace": "allegro",
                "numer_oferty": "111",
                "ilosc": 12,
                "nazwa": "Butelka PET 30ml",
            }
        )

        assert action.kind == "ustaw_stan_oferty"
        assert action.params["ilosc"] == 12
        assert "Butelka PET 30ml" in action.summary
        # Stan na półce zna tylko ORDLY - marketplace go nie widzi.
        assert action.outward is False

    def test_stan_bez_numeru_oferty_jest_odrzucany(self):
        with pytest.raises(AssistantActionError, match="numer_oferty"):
            build_action(
                {"rodzaj": "ustaw_stan_oferty", "marketplace": "allegro", "ilosc": 1}
            )

    @pytest.mark.parametrize("ilosc", [-1, MAX_QUANTITY + 1])
    def test_stan_poza_zakresem_jest_odrzucany(self, ilosc: int):
        with pytest.raises(AssistantActionError, match="miescic"):
            build_action(
                {
                    "rodzaj": "ustaw_stan_oferty",
                    "marketplace": "allegro",
                    "numer_oferty": "111",
                    "ilosc": ilosc,
                }
            )

    def test_stan_nieliczbowy_jest_odrzucany(self):
        with pytest.raises(AssistantActionError, match="liczba calkowita"):
            build_action(
                {
                    "rodzaj": "ustaw_stan_oferty",
                    "marketplace": "allegro",
                    "numer_oferty": "111",
                    "ilosc": "duzo",
                }
            )

    # ---- status zamówienia ----

    def test_oznaczenie_zamowienia_jest_oznaczone_jako_widoczne_na_zewnatrz(self):
        action = build_action(
            {
                "rodzaj": "oznacz_zamowienie",
                "numer_zamowienia": "A-1",
                "status": "wyslane",
                "kupujacy": "jan_kowalski",
            }
        )

        assert action.outward is True
        assert "jan_kowalski" in action.summary
        # Użytkownik ma z opisu wiedzieć, że to widzi kupujący.
        assert "Kupujący zobaczy" in action.summary

    def test_status_spoza_dwoch_dozwolonych_jest_odrzucany(self):
        # "anulowane" i cofanie statusu nie są w ogóle do zaproponowania.
        with pytest.raises(AssistantActionError, match="Status musi byc"):
            build_action(
                {
                    "rodzaj": "oznacz_zamowienie",
                    "numer_zamowienia": "A-1",
                    "status": "anulowane",
                }
            )

    # ---- odpowiedź w dyskusji ----

    def test_odpowiedz_w_dyskusji_jest_widoczna_na_zewnatrz(self):
        action = build_action(
            {
                "rodzaj": "odpowiedz_w_dyskusji",
                "numer_dyskusji": "D-7",
                "tresc": "Dzień dobry, paczka wyszła dziś rano.",
            }
        )

        assert action.outward is True
        assert action.params["tresc"].startswith("Dzień dobry")

    def test_pusta_odpowiedz_jest_odrzucana(self):
        with pytest.raises(AssistantActionError, match="tresc"):
            build_action(
                {"rodzaj": "odpowiedz_w_dyskusji", "numer_dyskusji": "D-7", "tresc": "   "}
            )

    def test_zbyt_dluga_odpowiedz_jest_odrzucana(self):
        with pytest.raises(AssistantActionError, match="limit"):
            build_action(
                {
                    "rodzaj": "odpowiedz_w_dyskusji",
                    "numer_dyskusji": "D-7",
                    "tresc": "a" * (MAX_REPLY_CHARS + 1),
                }
            )


# ----------------------------------------------------------------------
# Wykonanie
# ----------------------------------------------------------------------


def _offer(external_id: str, name: str) -> MarketplaceOffer:
    return MarketplaceOffer(
        marketplace="allegro",
        external_id=external_id,
        name=name,
        signature=None,
        available_stock=5,
        price=Decimal("19.99"),
        quantity_on_hand=None,
        synced_at=utc_now(),
    )


class TestExecutor:
    @pytest.mark.asyncio
    async def test_zatwierdzony_stan_ladzie_w_katalogu(self):
        catalog = FakeOfferCatalogRepository()
        catalog.offers[("allegro", "111")] = _offer("111", "Butelka PET 30ml")
        plugin = FakeMarketplacePlugin()
        executor = AssistantActionExecutor(
            orders_service=None,  # type: ignore[arg-type]
            offer_catalog_service=OfferCatalogService(
                plugin=plugin, catalog_repository=catalog
            ),
            issues_service=IssuesService(plugin),
        )
        action = build_action(
            {
                "rodzaj": "ustaw_stan_oferty",
                "marketplace": "allegro",
                "numer_oferty": "111",
                "ilosc": 12,
                "nazwa": "Butelka PET 30ml",
            }
        )

        message = await executor.apply(action)

        assert catalog.offers[("allegro", "111")].quantity_on_hand == 12
        assert "12 szt." in message

    @pytest.mark.asyncio
    async def test_zatwierdzona_odpowiedz_idzie_do_marketplace(self):
        plugin = FakeMarketplacePlugin()
        executor = AssistantActionExecutor(
            orders_service=None,  # type: ignore[arg-type]
            offer_catalog_service=OfferCatalogService(
                plugin=plugin, catalog_repository=FakeOfferCatalogRepository()
            ),
            issues_service=IssuesService(plugin),
        )
        action = build_action(
            {
                "rodzaj": "odpowiedz_w_dyskusji",
                "numer_dyskusji": "D-7",
                "tresc": "Paczka wyszła dziś rano.",
            }
        )

        await executor.apply(action)

        assert plugin.reply_calls == [("D-7", "Paczka wyszła dziś rano.")]
