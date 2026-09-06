"""
Testy pobierania asortymentu z Allegro: mapowanie i stronicowanie.

Stronicowanie sprawdzamy przez PRAWDZIWEGO klienta httpx wpiętego
w `httpx.MockTransport`, a nie przez podmianę `AllegroApiClient.get` na
własną funkcję. Podmieniony klient udowodniłby tylko, że pętla woła
metodę, którą sami napisaliśmy - a to właśnie kształt odpowiedzi i
sposób, w jaki httpx składa parametry `limit`/`offset`, decydują o tym,
czy sprzedawca z trzystoma ofertami dostanie wszystkie, czy pierwsze sto.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.domain.interfaces.token_store import StoredTokens, TokenStore
from app.infrastructure.plugins.allegro import client as client_module
from app.infrastructure.plugins.allegro.auth import TokenEncryptor
from app.infrastructure.plugins.allegro.config import AllegroConfig
from app.infrastructure.plugins.allegro.mapper import map_offer_to_domain
from app.infrastructure.plugins.allegro.plugin import AllegroPlugin
from app.utils.time import utc_now

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "allegro_responses"
_FERNET_KEY = "zh1Ry8Xz1sQnQm4nQhFqQ1vJb7bC8gYQ3nRt6kUuT2s="


class _FakeTokenStore(TokenStore):
    """Token store zwracający jeden ważny, zaszyfrowany token."""

    def __init__(self, encryptor: TokenEncryptor) -> None:
        self._tokens = StoredTokens(
            encrypted_access_token=encryptor.encrypt("test-access-token"),
            encrypted_refresh_token=encryptor.encrypt("test-refresh-token"),
            expires_at=utc_now() + timedelta(hours=1),
        )

    async def get_tokens(self, marketplace: str) -> StoredTokens | None:
        return self._tokens

    async def save_tokens(
        self, marketplace, encrypted_access_token, encrypted_refresh_token, expires_at
    ) -> None:
        raise AssertionError("Ważny token nie powinien być odświeżany")


@pytest.fixture
def config(monkeypatch) -> AllegroConfig:
    """Konfiguracja Allegro zbudowana ze zmiennych środowiskowych testu."""
    monkeypatch.setenv("ALLEGRO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("ALLEGRO_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ALLEGRO_TOKEN_ENCRYPTION_KEY", _FERNET_KEY)
    return AllegroConfig(_env_file=None)


def _install_transport(monkeypatch, handler) -> None:
    """
    Wpina `httpx.MockTransport` w klienta Allegro.

    `AllegroApiClient` tworzy `httpx.AsyncClient` sam, więc podmieniamy
    tę klasę w przestrzeni nazw modułu na fabrykę dokładającą transport.
    Cała reszta - nagłówki, serializacja parametrów, dekodowanie JSON,
    obsługa kodów błędów - zostaje prawdziwa.
    """
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(client_module.httpx, "AsyncClient", factory)


class TestMapowanieOferty:
    """Mapowanie surowej oferty z GET /sale/offers na encję katalogu."""

    def test_mapuje_pelna_oferte_z_przykladowego_jsona(self):
        """Sprawdza wszystkie pola, na których opiera się katalog."""
        raw = json.loads(
            (_FIXTURES_DIR / "sale_offers_sample.json").read_text(encoding="utf-8")
        )
        synced_at = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)

        offer = map_offer_to_domain(raw["offers"][0], "allegro", synced_at)

        assert offer.external_id == "12345678901"
        assert offer.name == "Butelka szklana 60 ml oranżowa z kroplomierzem"
        assert offer.signature == "BUT60-ORA"
        assert offer.status == "ACTIVE"
        assert offer.available_stock == 48
        assert offer.sold_count == 152
        assert offer.price == Decimal("12.90")
        assert offer.image_url == "https://a.allegroimg.com/original/11aabb/butelka60"
        assert offer.synced_at == synced_at

    def test_pusta_sygnatura_staje_sie_none(self):
        """
        Allegro pozwala zostawić sygnaturę pustą i zwraca wtedy `""`.
        Pusty string musi zejść do None, inaczej dwie oferty bez
        sygnatury wyglądałyby na ten sam produkt magazynowy.
        """
        raw = json.loads(
            (_FIXTURES_DIR / "sale_offers_sample.json").read_text(encoding="utf-8")
        )

        offer = map_offer_to_domain(raw["offers"][1], "allegro", utc_now())

        assert offer.signature is None

    def test_mapuje_oferte_bez_sekcji_external_i_zdjecia(self):
        """
        Mapper nie może zakładać, że wszystkie sekcje odpowiedzi są obecne.

        Trzecia oferta w przykładzie nie ma ani `external`, ani
        `primaryImage`. Katalog pobiera dziś wyłącznie oferty aktywne,
        ale odporność na niepełny wiersz to zadanie mappera, nie filtra -
        Allegro potrafi pominąć sekcję w każdej odpowiedzi.
        """
        raw = json.loads(
            (_FIXTURES_DIR / "sale_offers_sample.json").read_text(encoding="utf-8")
        )

        offer = map_offer_to_domain(raw["offers"][2], "allegro", utc_now())

        assert offer.signature is None
        assert offer.image_url is None
        assert offer.available_stock == 0

    def test_oferta_bez_ceny_i_zdjecia_nie_wywraca_mapowania(self):
        """Braki opcjonalnych pól to poprawny stan, nie błąd."""
        offer = map_offer_to_domain({"id": "999", "name": "Goła oferta"}, "allegro", utc_now())

        assert offer.price is None
        assert offer.image_url is None
        assert offer.available_stock == 0
        assert offer.status == "ACTIVE"


class TestFiltrStatusuPublikacji:
    """Katalog ma zawierać wyłącznie oferty mogące jeszcze sprzedać."""

    async def test_prosi_allegro_tylko_o_aktywne_oferty(self, config, monkeypatch):
        """
        Filtr musi iść w zapytaniu, a nie po pobraniu wszystkiego.

        Sprzedawca z długą historią ma zwykle wielokrotnie więcej ofert
        zakończonych niż wystawionych - odsiewanie ich lokalnie
        oznaczałoby ściąganie kilkunastu stron po to, żeby je zaraz
        wyrzucić.
        """
        seen_statuses: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_statuses.extend(request.url.params.get_list("publication.status"))
            return httpx.Response(200, json={"offers": [], "count": 0, "totalCount": 0})

        _install_transport(monkeypatch, handler)
        plugin = AllegroPlugin(
            config=config, token_store=_FakeTokenStore(TokenEncryptor(_FERNET_KEY))
        )

        await plugin.get_offers()

        assert seen_statuses == ["ACTIVE", "ACTIVATING"]

    async def test_nie_prosi_o_oferty_zakonczone(self, config, monkeypatch):
        """
        Wprost: `ENDED` i `INACTIVE` nie mogą pojawić się w zapytaniu.

        Osobny test od powyższego, bo to jest cała treść zgłoszenia -
        zakończone oferty zaśmiecały listę do powiązania.
        """
        seen_query: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_query.append(str(request.url))
            return httpx.Response(200, json={"offers": [], "count": 0, "totalCount": 0})

        _install_transport(monkeypatch, handler)
        plugin = AllegroPlugin(
            config=config, token_store=_FakeTokenStore(TokenEncryptor(_FERNET_KEY))
        )

        await plugin.get_offers()

        assert seen_query, "Nie poszło żadne zapytanie do Allegro"
        assert "ENDED" not in seen_query[0]
        assert "INACTIVE" not in seen_query[0]


class TestStronicowanieAsortymentu:
    """`get_offers` musi zejść po WSZYSTKICH stronach wyników."""

    async def test_pobiera_oferty_z_wielu_stron(self, config, monkeypatch):
        """
        Sprzedawca z 250 ofertami dostaje 250, a nie pierwsze 100.

        Serwer testowy odpowiada zgodnie z kontraktem Allegro: wycinek
        listy dla podanego `offset`/`limit` plus `totalCount` całości.
        """
        total = 250
        all_offers = [
            {
                "id": f"{100000 + index}",
                "name": f"Oferta {index}",
                "stock": {"available": index, "sold": 0},
                "sellingMode": {"price": {"amount": "9.99", "currency": "PLN"}},
                "publication": {"status": "ACTIVE"},
                "external": {"id": f"SKU-{index}"},
            }
            for index in range(total)
        ]
        seen_offsets: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/sale/offers"
            assert request.headers["Authorization"] == "Bearer test-access-token"
            offset = int(request.url.params.get("offset", 0))
            limit = int(request.url.params.get("limit", 100))
            seen_offsets.append(request.url.params.get("offset"))
            page = all_offers[offset : offset + limit]
            return httpx.Response(
                200, json={"offers": page, "count": len(page), "totalCount": total}
            )

        _install_transport(monkeypatch, handler)
        plugin = AllegroPlugin(
            config=config, token_store=_FakeTokenStore(TokenEncryptor(_FERNET_KEY))
        )

        offers = await plugin.get_offers()

        assert len(offers) == total
        assert seen_offsets == ["0", "100", "200"]
        assert offers[0].external_id == "100000"
        assert offers[-1].external_id == f"{100000 + total - 1}"
        assert offers[-1].signature == f"SKU-{total - 1}"

    async def test_konczy_na_pustej_stronie_gdy_total_count_klamie(self, config, monkeypatch):
        """
        Zabezpieczenie przed pętlą nieskończoną: gdy `totalCount` obiecuje
        więcej, niż serwer oddaje, pusta strona kończy chodzenie.
        """
        calls = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            offset = int(request.url.params.get("offset", 0))
            page = (
                [{"id": "1", "name": "Jedyna", "publication": {"status": "ACTIVE"}}]
                if offset == 0
                else []
            )
            return httpx.Response(
                200, json={"offers": page, "count": len(page), "totalCount": 9999}
            )

        _install_transport(monkeypatch, handler)
        plugin = AllegroPlugin(
            config=config, token_store=_FakeTokenStore(TokenEncryptor(_FERNET_KEY))
        )

        offers = await plugin.get_offers()

        assert len(offers) == 1
        assert calls["count"] == 2

    async def test_pusty_asortyment_to_poprawny_stan(self, config, monkeypatch):
        """Sprzedawca bez ofert dostaje pustą listę, nie wyjątek."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"offers": [], "count": 0, "totalCount": 0})

        _install_transport(monkeypatch, handler)
        plugin = AllegroPlugin(
            config=config, token_store=_FakeTokenStore(TokenEncryptor(_FERNET_KEY))
        )

        assert await plugin.get_offers() == []
