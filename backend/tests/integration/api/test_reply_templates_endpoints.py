"""
Testy HTTP endpointów `/api/v1/reply-templates/*`.

Kontrakt pola odpowiedzi w Dyskusjach (desktop i telefon) oraz listy
w Ustawieniach desktopu: aplikacje czytają `id`, `title` i `body` po
nazwie, a znaczniki `{...}` muszą przejść przez serwer NIETKNIĘTE -
podstawia je aplikacja, bo tylko ona zna wątek i zamówienie.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_container, get_session
from app.api.endpoints import reply_templates as reply_templates_endpoints
from app.api.errors import register_exception_handlers
from app.domain.entities.reply_template import ReplyTemplate
from app.domain.interfaces.reply_template_repository import ReplyTemplateRepository


class _MemoryRepository(ReplyTemplateRepository):
    """Szablony w pamięci - kolejność i `id` jak w SQLite."""

    def __init__(self) -> None:
        self.items: dict[int, ReplyTemplate] = {}
        self._next_id = 1

    async def list_all(self) -> list[ReplyTemplate]:
        return sorted(self.items.values(), key=lambda t: (t.position, t.id))

    async def add(self, title: str, body: str) -> ReplyTemplate:
        template = ReplyTemplate(id=self._next_id, title=title, body=body, position=self._next_id)
        self.items[template.id] = template
        self._next_id += 1
        return template

    async def update(self, template_id: int, title: str, body: str) -> ReplyTemplate | None:
        current = self.items.get(template_id)
        if current is None:
            return None
        updated = ReplyTemplate(id=current.id, title=title, body=body, position=current.position)
        self.items[template_id] = updated
        return updated

    async def delete(self, template_id: int) -> bool:
        return self.items.pop(template_id, None) is not None


class _StubContainer:
    def __init__(self) -> None:
        self.repository = _MemoryRepository()

    def reply_template_repository(self, _session=None) -> _MemoryRepository:
        return self.repository


@pytest.fixture
def container() -> _StubContainer:
    return _StubContainer()


@pytest.fixture
def client(container: _StubContainer) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(reply_templates_endpoints.router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_session] = lambda: None
    with TestClient(app) as test_client:
        yield test_client


class TestTworzenieIOdczyt:
    def test_znaczniki_przechodza_przez_serwer_nietkniete(self, client: TestClient):
        body = "Numer przesyłki: {numer_przesylki}. Pozdrawiam {login}"
        created = client.post("/api/v1/reply-templates", json={"title": "Wysłane", "body": body})

        assert created.status_code == 201
        assert created.json() == {"id": 1, "title": "Wysłane", "body": body}
        assert client.get("/api/v1/reply-templates").json() == [created.json()]

    def test_obcina_biale_znaki_na_brzegach(self, client: TestClient):
        created = client.post(
            "/api/v1/reply-templates", json={"title": "  Dzięki  ", "body": "\nDziękuję.\n"}
        )

        assert created.json()["title"] == "Dzięki"
        assert created.json()["body"] == "Dziękuję."

    @pytest.mark.parametrize("field", ["title", "body"])
    def test_same_spacje_to_nie_tresc(self, client: TestClient, field: str):
        payload = {"title": "Tytuł", "body": "Treść"}
        payload[field] = "   "

        response = client.post("/api/v1/reply-templates", json=payload)

        assert response.status_code == 422


class TestEdycjaIUsuwanie:
    def test_edycja_zmienia_tresc(self, client: TestClient):
        created = client.post("/api/v1/reply-templates", json={"title": "A", "body": "a"}).json()

        response = client.put(
            f"/api/v1/reply-templates/{created['id']}", json={"title": "A", "body": "nowa"}
        )

        assert response.status_code == 200
        assert response.json()["body"] == "nowa"

    def test_usuniety_znika_z_listy(self, client: TestClient):
        created = client.post("/api/v1/reply-templates", json={"title": "A", "body": "a"}).json()

        assert client.delete(f"/api/v1/reply-templates/{created['id']}").status_code == 204
        assert client.get("/api/v1/reply-templates").json() == []

    def test_brakujacy_szablon_to_404_z_wyjasnieniem(self, client: TestClient):
        put = client.put("/api/v1/reply-templates/42", json={"title": "A", "body": "a"})
        delete = client.delete("/api/v1/reply-templates/42")

        assert put.status_code == 404
        assert delete.status_code == 404
        assert "drugim urządzeniu" in put.json()["detail"]
