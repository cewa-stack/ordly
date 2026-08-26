"""
Testy HTTP endpointu `GET /api/v1/mail/messages/{message_id}/body`.

Na warstwie HTTP widać dwie rzeczy, których nie złapie test serwisu.
Pierwsza to identyfikator w ścieżce: Message-ID zawiera `<`, `>` i `@`,
więc trasa musi przeżyć zakodowanie w URL-u i wrócić do serwisu bez
zmian - inaczej wiadomość "nie istnieje" mimo że leży w skrzynce.
Druga to kształt JSON-a (`html_body` / `plain_body`), bo to kontrakt
aplikacji desktopowej i PWA.
"""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import get_container, get_session
from app.api.endpoints import mail as mail_endpoints
from app.api.errors import register_exception_handlers
from app.core.config import MailWatchSettings
from app.infrastructure.mail.imap_watcher import ImapConnectionError
from app.infrastructure.mail.mime import MailBodies
from app.services.mailbox_service import MailboxService
from tests.fakes.fake_mail_repository import FakeMailRepository

MESSAGE_ID = "<01000198.7f2a@allegromail.pl>"

_HTML = (
    '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">'
    '<html lang="pl"><head><style>body{font-family:Arial}</style></head>'
    "<body><p>Dzie&#324; dobry,</p><p>masz now&#261; wiadomo&#347;&#263;.</p>"
    "</body></html>"
)


class _StubWatcher:
    """Watcher IMAP bez IMAP-a - oddaje z góry ustaloną treść albo błąd."""

    def __init__(self, bodies: MailBodies | None = None, raises: Exception | None = None):
        self.bodies = bodies
        self.raises = raises

    async def fetch_new_from_senders(self, senders, since):
        return []

    async def fetch_bodies_by_message_id(self, message_id: str) -> MailBodies | None:
        if self.raises is not None:
            raise self.raises
        return self.bodies


class _StubContainer:
    def __init__(self, watcher: _StubWatcher, configured: bool = True) -> None:
        self._watcher = watcher
        self._settings = (
            MailWatchSettings(
                IMAP_HOST="imap.gmail.com",
                IMAP_USER="sklep@gmail.com",
                IMAP_PASS=SecretStr("haslo-aplikacji"),
            )
            if configured
            else MailWatchSettings(_env_file=None)
        )

    def mailbox_service(self, _session=None) -> MailboxService:
        return MailboxService(
            FakeMailRepository(), self._settings, watcher_factory=lambda: self._watcher
        )


def _client(container: _StubContainer) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(mail_endpoints.router, prefix="/api/v1")
    register_exception_handlers(app)
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_session] = lambda: None
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client() -> Iterator[TestClient]:
    watcher = _StubWatcher(bodies=MailBodies(html=_HTML, text=None))
    yield from _client(_StubContainer(watcher))


def _body_url(message_id: str = MESSAGE_ID) -> str:
    return f"/api/v1/mail/messages/{quote(message_id, safe='')}/body"


class TestGetMailBody:
    def test_zwraca_html_i_tekst_w_osobnych_polach(self, client: TestClient):
        response = client.get(_body_url())

        assert response.status_code == 200
        payload = response.json()
        assert payload["html_body"].startswith("<!DOCTYPE HTML")
        assert payload["plain_body"] is not None

    def test_plain_body_powstaje_z_html_gdy_mail_nie_ma_czesci_tekstowej(
        self, client: TestClient
    ):
        """
        Allegro wysyła powiadomienia jako sam HTML. Bez tego przeliczenia
        widok bez renderera HTML nie miałby co pokazać - i właśnie stąd
        wziął się link "Otwórz pełną wiadomość w Gmail" jako jedyne
        wyjście.
        """
        payload = client.get(_body_url()).json()

        plain = payload["plain_body"]
        assert "<" not in plain
        assert "DOCTYPE" not in plain
        assert "font-family" not in plain
        assert "Dzień dobry," in plain
        assert "masz nową wiadomość." in plain

    def test_message_id_z_nawiasami_katowymi_dociera_bez_zmian(self):
        """`<`, `>` i `@` w identyfikatorze muszą przeżyć trasę HTTP."""
        watcher = _StubWatcher(bodies=MailBodies(html=None, text="tresc"))
        received: list[str] = []

        original = watcher.fetch_bodies_by_message_id

        async def spy(message_id: str):
            received.append(message_id)
            return await original(message_id)

        watcher.fetch_bodies_by_message_id = spy  # type: ignore[method-assign]

        for test_client in _client(_StubContainer(watcher)):
            response = test_client.get(_body_url())
            assert response.status_code == 200
            assert received == [MESSAGE_ID]

    def test_brak_maila_na_serwerze_to_404(self):
        for test_client in _client(_StubContainer(_StubWatcher(bodies=None))):
            response = test_client.get(_body_url())

            assert response.status_code == 404
            assert "skrzynce" in response.json()["detail"]

    def test_nieskonfigurowany_imap_to_503_z_nazwami_zmiennych(self):
        container = _StubContainer(_StubWatcher(), configured=False)
        for test_client in _client(container):
            response = test_client.get(_body_url())

            assert response.status_code == 503
            assert "IMAP_USER" in response.json()["detail"]

    def test_awaria_polaczenia_imap_to_502_z_powodem(self):
        watcher = _StubWatcher(raises=ImapConnectionError("Logowanie IMAP odrzucone"))
        for test_client in _client(_StubContainer(watcher)):
            response = test_client.get(_body_url())

            assert response.status_code == 502
            assert "Logowanie IMAP odrzucone" in response.json()["detail"]

    def test_trasa_body_nie_koliduje_z_mark_read(self, client: TestClient):
        """
        Obie trasy mają ten sam prefiks `/mail/messages/{message_id}/...`,
        więc warto mieć dowód, że FastAPI rozróżnia je po sufiksie i
        metodzie, a nie zjada jednej drugą.
        """
        assert client.get(_body_url()).status_code == 200
        assert (
            client.post(
                f"/api/v1/mail/messages/{quote(MESSAGE_ID, safe='')}/mark-read"
            ).status_code
            == 204
        )
