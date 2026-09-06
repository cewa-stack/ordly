"""
Testy HTTP endpointów `/api/v1/ordlak/*`.

To jest kontrakt między backendem a aplikacją desktopową: kształt JSON-a
i kody błędów. Testy serwisu nie złapałyby literówki w nazwie pola ani
złego kodu HTTP, bo omijają warstwę HTTP - a właśnie tam rozjeżdżają się
dwie strony.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import get_container, get_session
from app.api.endpoints import ordlak as ordlak_endpoints
from app.core.config import MailWatchSettings, OrdlakSettings
from app.services.dashboard_service import DashboardService
from app.services.inventory_service import InventoryService
from app.services.issues_service import IssuesService
from app.services.mailbox_service import MailboxService
from app.services.ordlak_assistant_service import OrdlakAssistantService
from app.services.returns_service import ReturnsService
from app.services.search_service import SearchService
from tests.fakes.fake_anthropic import (
    FakeAnthropic,
    FakeResponse,
    StubHealthService,
    TextBlock,
    ToolUseBlock,
)
from tests.fakes.fake_inventory_repository import FakeInventoryRepository
from tests.fakes.fake_mail_repository import FakeMailRepository
from tests.fakes.fake_marketplace_plugin import FakeMarketplacePlugin
from tests.fakes.fake_order_repository import FakeOrderRepository
from tests.fakes.fake_ordlak_conversation_repository import (
    FakeOrdlakConversationRepository,
)
from tests.fakes.fake_return_repository import FakeReturnRepository


class _StubContainer:
    """
    Kontener podstawiany zamiast prawdziwego - trzyma repozytoria
    w pamięci, żeby narzędzia asystenta miały co czytać.
    """

    def __init__(self, configured: bool = True) -> None:
        self.orders = FakeOrderRepository()
        self.inventory = FakeInventoryRepository()
        self.returns = FakeReturnRepository()
        self.plugin = FakeMarketplacePlugin()
        self.mail = FakeMailRepository()
        # Jedno repozytorium rozmow na kontener - endpoint czatu i lista
        # rozmow musza widziec te same watki, mimo osobnych sesji.
        self.conversations = FakeOrdlakConversationRepository()
        self.client = FakeAnthropic([FakeResponse([TextBlock("Dziś 2 zamówienia.")])])
        self.settings = OrdlakSettings(
            _env_file=None,
            ANTHROPIC_API_KEY=SecretStr("sk-test" if configured else ""),
            ANTHROPIC_MODEL="claude-sonnet-5",
        )

    def ordlak_settings(self) -> OrdlakSettings:
        return self.settings

    def session_scope(self):
        return _NullSessionScope()

    def ordlak_assistant_service(self, _session=None) -> OrdlakAssistantService:
        return OrdlakAssistantService(
            settings=self.settings,
            order_repository=self.orders,
            inventory_service=InventoryService(self.inventory),
            returns_service=ReturnsService(self.returns),
            dashboard_service=DashboardService(self.orders, self.inventory),
            health_service=StubHealthService(),
            search_service=SearchService(self.orders),
            issues_service=IssuesService(self.plugin),
            mailbox_service=MailboxService(
                self.mail,
                MailWatchSettings(_env_file=None, IMAP_USER="", IMAP_PASS=SecretStr("")),
                watcher_factory=lambda: None,
            ),
            conversation_repository=self.conversations,
            # Brak klucza = brak fabryki, więc serwis idzie ścieżką
            # "nie skonfigurowano" dokładnie jak na prawdziwym Pi.
            client_factory=(lambda: self.client) if self.settings.enabled else None,
        )


class _NullSessionScope:
    """Endpointy zapisujace otwieraja wlasny zakres sesji - tu nie ma bazy."""

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


class TestStatus:
    def test_zwraca_model_i_informacje_o_kluczu(self, client: TestClient):
        response = client.get("/api/v1/ordlak/status")

        assert response.status_code == 200
        assert response.json() == {"configured": True, "model": "claude-sonnet-5"}

    def test_bez_klucza_zglasza_brak_konfiguracji(self):
        with _build_client(_StubContainer(configured=False)) as test_client:
            response = test_client.get("/api/v1/ordlak/status")

        assert response.json()["configured"] is False


class TestChat:
    def test_zwraca_odpowiedz_numer_watku_i_uzyte_narzedzia(
        self, client: TestClient, container: _StubContainer
    ):
        container.client.responses = [
            FakeResponse([ToolUseBlock("stan_systemu")], stop_reason="tool_use"),
            FakeResponse([TextBlock("Wszystko działa.")]),
        ]

        response = client.post("/api/v1/ordlak/chat", json={"message": "Jak leci?"})

        assert response.status_code == 200
        body = response.json()
        assert body["reply"] == "Wszystko działa."
        assert body["used_tools"] == ["stan_systemu"]
        assert body["conversation_id"] > 0

    def test_kolejne_pytanie_trafia_do_tego_samego_watku(self, client: TestClient):
        first = client.post("/api/v1/ordlak/chat", json={"message": "Ile sprzedałem?"})
        thread_id = first.json()["conversation_id"]

        second = client.post(
            "/api/v1/ordlak/chat",
            json={"message": "A wczoraj?", "conversation_id": thread_id},
        )

        assert second.json()["conversation_id"] == thread_id

    def test_puste_pytanie_odrzucone(self, client: TestClient):
        response = client.post("/api/v1/ordlak/chat", json={"message": ""})

        assert response.status_code == 422

    def test_nieistniejacy_watek_daje_404(self, client: TestClient):
        response = client.post(
            "/api/v1/ordlak/chat",
            json={"message": "Jak leci?", "conversation_id": 999},
        )

        assert response.status_code == 404

    def test_brak_klucza_api_daje_503(self):
        with _build_client(_StubContainer(configured=False)) as test_client:
            response = test_client.post("/api/v1/ordlak/chat", json={"message": "Jak leci?"})

        assert response.status_code == 503
        assert "ANTHROPIC_API_KEY" in response.json()["detail"]

    def test_blad_modelu_daje_422_z_komunikatem_po_polsku(
        self, client: TestClient, container: _StubContainer
    ):
        blad = Exception("boom")
        blad.status_code = 429
        container.client.raise_error = blad

        response = client.post("/api/v1/ordlak/chat", json={"message": "Jak leci?"})

        assert response.status_code == 422
        assert "429" in response.json()["detail"]


class TestRozmowy:
    def test_lista_pokazuje_tytul_i_licznik_bez_tresci(self, client: TestClient):
        client.post("/api/v1/ordlak/chat", json={"message": "Ile sprzedałem w tym tygodniu?"})

        response = client.get("/api/v1/ordlak/conversations")

        assert response.status_code == 200
        watek = response.json()[0]
        assert watek["title"] == "Ile sprzedałem w tym tygodniu?"
        assert watek["message_count"] == 2
        assert watek["messages"] == []

    def test_pojedynczy_watek_oddaje_pelna_historie(self, client: TestClient):
        thread_id = client.post(
            "/api/v1/ordlak/chat", json={"message": "Ile sprzedałem?"}
        ).json()["conversation_id"]

        response = client.get(f"/api/v1/ordlak/conversations/{thread_id}")

        assert response.status_code == 200
        wiadomosci = response.json()["messages"]
        assert [m["role"] for m in wiadomosci] == ["user", "assistant"]
        assert wiadomosci[0]["content"] == "Ile sprzedałem?"

    def test_nieistniejacy_watek_daje_404(self, client: TestClient):
        assert client.get("/api/v1/ordlak/conversations/999").status_code == 404

    def test_usuwanie_zwraca_204_a_potem_404(self, client: TestClient):
        thread_id = client.post(
            "/api/v1/ordlak/chat", json={"message": "Do skasowania"}
        ).json()["conversation_id"]

        assert client.delete(f"/api/v1/ordlak/conversations/{thread_id}").status_code == 204
        assert client.delete(f"/api/v1/ordlak/conversations/{thread_id}").status_code == 404
        assert client.get(f"/api/v1/ordlak/conversations/{thread_id}").status_code == 404
