"""
Testy HTTP endpointów `/api/v1/ordlak/*`.

To jest kontrakt między backendem a aplikacją desktopową: nazwy pól
`multipart/form-data`, kształt JSON-a i kody błędów. Testy serwisu nie
złapałyby literówki w nazwie pola formularza ani złego kodu HTTP, bo
omijają warstwę HTTP - a właśnie tam rozjeżdżają się dwie strony.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import get_container, get_session
from app.api.endpoints import ordlak as ordlak_endpoints
from app.core.config import OrdlakSettings
from app.services.ordlak_service import OrdlakService
from tests.fakes.fake_ordlak_repository import FakeOrdlakRepository

TYTUL = "Kubek ceramiczny biały 350 ml porcelana matowa do kawy herbaty prezent"
OPIS = "<p>Kubek ceramiczny 350 ml.</p>"


class _Block:
    type = "tool_use"

    def __init__(self, payload: dict) -> None:
        self.input = payload


class _Response:
    stop_reason = "tool_use"

    def __init__(self, payload: dict) -> None:
        self.content = [_Block(payload)]


class _Messages:
    def __init__(self, owner: _FakeAnthropic) -> None:
        self._owner = owner

    async def create(self, **kwargs):
        self._owner.calls.append(kwargs)
        return _Response(
            {
                "title": TYTUL,
                "description_html": OPIS,
                "condition_notes": "Bez rys." if self._owner.saw_images(kwargs) else "",
            }
        )


class _FakeAnthropic:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.messages = _Messages(self)

    @staticmethod
    def saw_images(kwargs: dict) -> bool:
        content = kwargs["messages"][0]["content"]
        return any(block.get("type") == "image" for block in content)


class _StubContainer:
    """
    Kontener podstawiany zamiast prawdziwego - trzyma jedno repozytorium
    w pamięci, żeby `generate` i `history` widziały te same dane.
    """

    def __init__(self, configured: bool = True) -> None:
        self.repository = FakeOrdlakRepository()
        self.client = _FakeAnthropic()
        self.settings = OrdlakSettings(
            _env_file=None,
            ANTHROPIC_API_KEY=SecretStr("sk-test" if configured else ""),
            ANTHROPIC_MODEL="claude-sonnet-5",
            ORDLAK_MAX_PHOTO_SIZE_MB=5,
        )

    def ordlak_settings(self) -> OrdlakSettings:
        return self.settings

    def ordlak_service(self, _session=None) -> OrdlakService:
        return OrdlakService(
            repository=self.repository,
            settings=self.settings,
            # Brak klucza = brak fabryki, więc serwis idzie ścieżką
            # "nie skonfigurowano" dokładnie jak na prawdziwym Pi.
            client_factory=(lambda: self.client) if self.settings.enabled else None,
        )

    def session_scope(self):
        return _NullSessionScope()


class _NullSessionScope:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *_args):
        return False


def _build_client(container: _StubContainer) -> TestClient:
    app = FastAPI()
    app.include_router(ordlak_endpoints.router, prefix="/api/v1")
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_session] = lambda: None
    return TestClient(app)


@pytest.fixture
def container() -> _StubContainer:
    return _StubContainer()


@pytest.fixture
def client(container: _StubContainer) -> Iterator[TestClient]:
    with _build_client(container) as test_client:
        yield test_client


def _form(**overrides) -> dict[str, str]:
    data = {
        "note": "Biały kubek ceramiczny 350 ml",
        "condition": "new",
        "purchase_cost": "25.0",
        "inbound_shipping_cost": "8.0",
        "buyer_shipping_cost": "12.0",
        "commission_percent": "10.0",
        "target_margin_percent": "30.0",
    }
    data.update({key: str(value) for key, value in overrides.items()})
    return data


class TestStatus:
    def test_zwraca_limity_i_model(self, client: TestClient):
        response = client.get("/api/v1/ordlak/status")

        assert response.status_code == 200
        body = response.json()
        assert body["configured"] is True
        assert body["model"] == "claude-sonnet-5"
        assert body["max_photos"] == 3
        assert body["max_photo_size_mb"] == 5

    def test_bez_klucza_zglasza_brak_konfiguracji(self):
        with _build_client(_StubContainer(configured=False)) as test_client:
            response = test_client.get("/api/v1/ordlak/status")

        assert response.json()["configured"] is False


class TestGenerate:
    def test_zwraca_pelny_wynik(self, client: TestClient):
        response = client.post("/api/v1/ordlak/generate", data=_form())

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == TYTUL
        assert body["description_html"] == OPIS
        assert body["condition"] == "new"
        assert body["photo_count"] == 0
        assert body["title_below_target"] is False
        assert body["price_breakdown"]["suggested_price"] == 57.0
        assert body["price_breakdown"]["commission_amount"] == 6.9
        assert body["id"] > 0

    def test_przyjmuje_zdjecia_jako_multipart(
        self, client: TestClient, container: _StubContainer
    ):
        files = [
            ("photos", ("a.jpg", b"\xff\xd8fake", "image/jpeg")),
            ("photos", ("b.png", b"\x89PNGfake", "image/png")),
        ]

        response = client.post("/api/v1/ordlak/generate", data=_form(), files=files)

        assert response.status_code == 200
        assert response.json()["photo_count"] == 2
        assert container.client.saw_images(container.client.calls[0]) is True

    def test_koszty_wysylki_maja_wartosci_domyslne(self, client: TestClient):
        """Desktop wysyła te pola zawsze, ale API nie może ich wymagać."""
        minimalny = {
            "note": "Kubek",
            "condition": "new",
            "purchase_cost": "25.0",
            "commission_percent": "10.0",
            "target_margin_percent": "30.0",
        }

        response = client.post("/api/v1/ordlak/generate", data=minimalny)

        assert response.status_code == 200
        breakdown = response.json()["price_breakdown"]
        assert breakdown["inbound_shipping_cost"] == 0.0
        assert breakdown["buyer_shipping_cost"] == 0.0

    def test_zla_prowizja_daje_422_z_komunikatem_po_polsku(self, client: TestClient):
        response = client.post(
            "/api/v1/ordlak/generate",
            data=_form(commission_percent=70.0, target_margin_percent=40.0),
        )

        assert response.status_code == 422
        assert "100%" in response.json()["detail"]

    def test_cztery_zdjecia_daja_422(self, client: TestClient):
        files = [("photos", (f"{i}.jpg", b"\xff\xd8fake", "image/jpeg")) for i in range(4)]

        response = client.post("/api/v1/ordlak/generate", data=_form(), files=files)

        assert response.status_code == 422
        assert "Maksymalnie 3" in response.json()["detail"]

    def test_nieznany_stan_daje_422(self, client: TestClient):
        response = client.post("/api/v1/ordlak/generate", data=_form(condition="zepsuty"))

        assert response.status_code == 422

    def test_brak_klucza_api_daje_503(self):
        with _build_client(_StubContainer(configured=False)) as test_client:
            response = test_client.post("/api/v1/ordlak/generate", data=_form())

        assert response.status_code == 503
        assert "ANTHROPIC_API_KEY" in response.json()["detail"]


class TestHistoriaIFinalize:
    def test_historia_zawiera_wygenerowana_oferte(self, client: TestClient):
        client.post("/api/v1/ordlak/generate", data=_form())

        response = client.get("/api/v1/ordlak/history")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["title"] == TYTUL
        assert items[0]["is_edited"] is False
        assert items[0]["price_breakdown"]["suggested_price"] == 57.0

    def test_finalize_zapisuje_poprawki(self, client: TestClient):
        generation_id = client.post("/api/v1/ordlak/generate", data=_form()).json()["id"]

        response = client.post(
            f"/api/v1/ordlak/{generation_id}/finalize",
            json={
                "final_title": "Poprawiony tytuł oferty na Allegro",
                "final_description_html": "<p>Poprawiony opis</p>",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Poprawiony tytuł oferty na Allegro"
        assert body["is_edited"] is True

    def test_finalize_nieistniejacej_generacji_daje_404(self, client: TestClient):
        response = client.post(
            "/api/v1/ordlak/999/finalize",
            json={"final_title": "tytuł", "final_description_html": "<p>opis</p>"},
        )

        assert response.status_code == 404

    def test_finalize_pustego_tytulu_odrzucony(self, client: TestClient):
        generation_id = client.post("/api/v1/ordlak/generate", data=_form()).json()["id"]

        response = client.post(
            f"/api/v1/ordlak/{generation_id}/finalize",
            json={"final_title": "", "final_description_html": "<p>opis</p>"},
        )

        assert response.status_code == 422
