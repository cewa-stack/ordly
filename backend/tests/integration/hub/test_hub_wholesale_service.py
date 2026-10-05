"""
Zamówienia do hurtowni z Control Huba - prawdziwa baza SQLite, udawany SMTP.

Mail do hurtowni jest nieodwracalny, więc testy pilnują przede wszystkim,
żeby nie wyszedł dwa razy, nie wyszedł z innymi pozycjami niż na podglądzie
i nie poszedł pod adres spoza listy hurtowni. Treść ma być taka sama jak
z desktopu (`wholesalerTemplate.ts`).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest

from app.domain.exceptions.domain_exceptions import MailNotConfiguredError, MailSendError
from app.services.hub_wholesale_service import (
    TOPIC_WHOLESALE_CATALOG,
    TOPIC_WHOLESALE_ITEMS,
    TOPIC_WHOLESALE_PREVIEW,
    TOPIC_WHOLESALE_RESULT,
    HubWholesaleService,
)
from tests.integration.hub.conftest import RecordingPublisher, SessionScope

TEST_SENDER = "sklep@example.com"

TEMPLATE_STD = {
    "id": "tpl-std",
    "name": "Standardowe zamówienie",
    "subject": "Zamówienie - {produkty}",
    "body": (
        "Dzień dobry {osoba_kontaktowa},\n\nChciałbym złożyć zamówienie:\n\n"
        "{lista_pozycji}\n\n{hurtownia}, {data}\nPozdrawiam"
    ),
    "inquirySubject": "Zapytanie",
    "inquiryBody": "Dzień dobry {osoba_kontaktowa},\n\n",
    "isDefault": True,
}
TEMPLATE_PILNE = {
    **TEMPLATE_STD,
    "id": "tpl-pilne",
    "name": "Pilne",
    "subject": "PILNE: {produkty}",
    "isDefault": False,
}

CATALOG: dict[str, Any] = {
    "wholesalers": [
        {
            "id": "w-1",
            "name": "Hurt-Pol",
            "email": "zamowienia@hurtpol.example",
            "contactPerson": "Panie Marku",
            "items": [
                {"name": "Kubek 300 ml", "quantity": 24},
                {"name": "Talerz płaski", "quantity": 12},
                {"name": "Miska", "quantity": 6},
            ],
        },
        {
            "id": "w-2",
            "name": "Szkło-Bis",
            "email": "biuro@szklobis.example",
            "items": [{"name": "Szklanka", "quantity": 36}],
            "templateId": "tpl-pilne",
        },
    ],
    "templates": [TEMPLATE_STD, TEMPLATE_PILNE],
}


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail_with: Exception | None = None

    async def send(self, to: str, subject: str, body: str) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append((to, subject, body))


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 6, 8, 0, 0)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def publisher() -> RecordingPublisher:
    return RecordingPublisher()


@pytest.fixture
def clock() -> Clock:
    return Clock()


def _service(
    session_scope: SessionScope,
    mailer: FakeMailer,
    publisher: RecordingPublisher,
    clock: Clock,
    test_mode: bool,
) -> HubWholesaleService:
    return HubWholesaleService(
        session_scope_factory=session_scope,
        mailer_factory=lambda: mailer,
        publisher=publisher,
        test_mode=test_mode,
        test_recipient=TEST_SENDER,
        today=lambda: date(2026, 10, 6),
        now=clock,
    )


@pytest.fixture
def live(session_scope, mailer, publisher, clock) -> HubWholesaleService:
    """Tryb prawdziwej wysyłki do hurtowni."""
    return _service(session_scope, mailer, publisher, clock, test_mode=False)


@pytest.fixture
def test_mode(session_scope, mailer, publisher, clock) -> HubWholesaleService:
    return _service(session_scope, mailer, publisher, clock, test_mode=True)


async def _version(service: HubWholesaleService) -> str:
    return await service.save_catalog(CATALOG)


def _request(version: str, **overrides: Any) -> dict[str, Any]:
    return {
        "request_id": "req-1",
        "version": version,
        "wholesaler_id": "w-1",
        "template_id": "tpl-std",
        "items": [0, 2],
        **overrides,
    }


class TestKatalog:
    async def test_hub_dostaje_liste_hurtowni_z_szablonem_przypisanym(
        self, live: HubWholesaleService, publisher: RecordingPublisher
    ):
        version = await _version(live)

        await live.handle_get({})

        [catalog] = publisher.on(TOPIC_WHOLESALE_CATALOG)
        assert catalog["version"] == version
        assert catalog["test_mode"] is False
        assert [(w["name"], w["template_id"], w["items"]) for w in catalog["wholesalers"]] == [
            ("Hurt-Pol", "tpl-std", 3),
            ("Szkło-Bis", "tpl-pilne", 1),
        ]
        assert [t["name"] for t in catalog["templates"]] == ["Standardowe zamówienie", "Pilne"]
        # Adresu hurtowni Hub w ogóle nie dostaje.
        assert "email" not in str(catalog)

    async def test_pozycje_jednej_hurtowni(
        self, live: HubWholesaleService, publisher: RecordingPublisher
    ):
        await _version(live)

        await live.handle_get({"wholesaler_id": "w-1"})
        await live.handle_get({"wholesaler_id": "nie-ma"})

        found, missing = publisher.on(TOPIC_WHOLESALE_ITEMS)
        assert found["items"] == [
            {"name": "Kubek 300 ml", "qty": 24},
            {"name": "Talerz płaski", "qty": 12},
            {"name": "Miska", "qty": 6},
        ]
        assert missing["ok"] is False

    async def test_przed_pierwsza_kopia_z_desktopu(
        self, live: HubWholesaleService, publisher: RecordingPublisher
    ):
        await live.handle_get({})
        result = await live.send(_request(""))

        assert publisher.on(TOPIC_WHOLESALE_CATALOG)[0]["wholesalers"] == []
        assert result["status"] == "error"
        assert "otwórz ORDLY na komputerze" in result["message"]


class TestTresc:
    async def test_mail_jak_z_desktopu(self, live: HubWholesaleService, mailer: FakeMailer):
        version = await _version(live)

        result = await live.send(_request(version))

        assert result["status"] == "sent"
        [(to, subject, body)] = mailer.sent
        assert to == "zamowienia@hurtpol.example"
        assert subject == "Zamówienie - kilka produktów"
        assert body == (
            "Dzień dobry Panie Marku,\n\nChciałbym złożyć zamówienie:\n\n"
            "- Kubek 300 ml - ilość: 24 szt.\n- Miska - ilość: 6 szt.\n\n"
            "Hurt-Pol, 06.10.2026\nPozdrawiam"
        )

    async def test_bez_pozycji_idzie_zapytanie_a_bez_osoby_znika_spacja(
        self, live: HubWholesaleService, mailer: FakeMailer, publisher: RecordingPublisher
    ):
        version = await _version(live)

        await live.handle_preview(
            _request(version, wholesaler_id="w-2", template_id=None, items=[])
        )
        await live.send(_request(version, wholesaler_id="w-2", template_id=None, items=[]))

        [preview] = publisher.on(TOPIC_WHOLESALE_PREVIEW)
        assert preview["inquiry"] is True
        assert preview["template"] == "Standardowe zamówienie"
        [(_, subject, body)] = mailer.sent
        assert (subject, body) == ("Zapytanie", "Dzień dobry,\n\n")

    async def test_szablon_wybrany_na_hubie(
        self, live: HubWholesaleService, mailer: FakeMailer
    ):
        version = await _version(live)

        await live.send(_request(version, template_id="tpl-pilne", items=[1]))

        assert mailer.sent[0][1] == "PILNE: Talerz płaski"


class TestBezpieczenstwo:
    async def test_ta_sama_prosba_drugi_raz_nie_wysyla_maila(
        self, live: HubWholesaleService, mailer: FakeMailer, publisher: RecordingPublisher
    ):
        version = await _version(live)

        await live.handle_send(_request(version))
        await live.handle_send(_request(version))

        first, second = publisher.on(TOPIC_WHOLESALE_RESULT)
        assert first["status"] == "sent"
        assert second["status"] == "already_sent"
        assert len(mailer.sent) == 1

    async def test_powtorka_w_15_minut_wymaga_potwierdzenia(
        self,
        live: HubWholesaleService,
        mailer: FakeMailer,
        clock: Clock,
        publisher: RecordingPublisher,
    ):
        version = await _version(live)
        await live.send(_request(version))
        clock.now += timedelta(minutes=7)

        await live.handle_preview(_request(version, request_id="req-2"))
        blocked = await live.send(_request(version, request_id="req-2"))
        confirmed = await live.send(
            _request(version, request_id="req-2", confirm_duplicate=True)
        )

        assert publisher.on(TOPIC_WHOLESALE_PREVIEW)[0]["duplicate_minutes"] == 7
        assert (blocked["status"], blocked["duplicate_minutes"]) == ("duplicate", 7)
        assert confirmed["status"] == "sent"
        assert len(mailer.sent) == 2

    async def test_inne_pozycje_albo_po_15_minutach_bez_pytania(
        self, live: HubWholesaleService, mailer: FakeMailer, clock: Clock
    ):
        version = await _version(live)
        await live.send(_request(version))

        other_items = await live.send(_request(version, request_id="req-2", items=[1]))
        clock.now += timedelta(minutes=16)
        later = await live.send(_request(version, request_id="req-3"))

        assert (other_items["status"], later["status"]) == ("sent", "sent")
        assert len(mailer.sent) == 3

    async def test_stara_lista_z_huba_jest_odrzucana(
        self, live: HubWholesaleService, mailer: FakeMailer
    ):
        old_version = await _version(live)
        changed = {
            **CATALOG,
            "wholesalers": [CATALOG["wholesalers"][1], CATALOG["wholesalers"][0]],
        }
        await live.save_catalog(changed)

        result = await live.send(_request(old_version))

        assert result["status"] == "error"
        assert "zmieniła się" in result["message"]
        assert mailer.sent == []

    @pytest.mark.parametrize(
        "items", [[3], [-1], ["0"], "0,1"], ids=["poza-lista", "ujemny", "tekst", "nie-lista"]
    )
    async def test_zle_pozycje(
        self, live: HubWholesaleService, mailer: FakeMailer, items: Any
    ):
        version = await _version(live)

        result = await live.send(_request(version, items=items))

        assert result["status"] == "error"
        assert mailer.sent == []

    async def test_adres_tylko_z_listy_hurtowni(
        self, live: HubWholesaleService, mailer: FakeMailer
    ):
        version = await _version(live)

        await live.send(_request(version, to="ktos@obcy.example", email="ktos@obcy.example"))

        assert mailer.sent[0][0] == "zamowienia@hurtpol.example"

    async def test_blad_smtp_mozna_ponowic_ta_sama_prosba(
        self, live: HubWholesaleService, mailer: FakeMailer
    ):
        version = await _version(live)
        mailer.fail_with = MailSendError("535 bad login")
        failed = await live.send(_request(version))
        mailer.fail_with = None
        retried = await live.send(_request(version))

        assert failed["status"] == "error"
        assert "535" in failed["message"]
        assert retried["status"] == "sent"
        assert len(mailer.sent) == 1

    async def test_brak_smtp(self, live: HubWholesaleService, mailer: FakeMailer):
        version = await _version(live)
        mailer.fail_with = MailNotConfiguredError()

        result = await live.send(_request(version))

        assert result["status"] == "error"
        assert "SMTP" in result["message"]


class TestTrybTestowy:
    async def test_mail_idzie_do_nadawcy_z_dopiskiem(
        self, test_mode: HubWholesaleService, mailer: FakeMailer, publisher: RecordingPublisher
    ):
        version = await _version(test_mode)

        await test_mode.handle_preview(_request(version))
        result = await test_mode.send(_request(version))

        [preview] = publisher.on(TOPIC_WHOLESALE_PREVIEW)
        assert (preview["test_mode"], preview["send_to"]) == (True, TEST_SENDER)
        assert preview["to"] == "zamowienia@hurtpol.example"
        [(to, subject, body)] = mailer.sent
        assert to == TEST_SENDER
        assert subject == "[TEST Hub -> Hurt-Pol] Zamówienie - kilka produktów"
        assert "Hurt-Pol <zamowienia@hurtpol.example>" in body
        assert "HUB_WHOLESALE_TEST_MODE=false" in body
        assert result["message"] == f"Wysłano TEST na {TEST_SENDER}"

    async def test_proba_testowa_nie_blokuje_prawdziwej(
        self, session_scope, mailer, publisher, clock
    ):
        tester = _service(session_scope, mailer, publisher, clock, test_mode=True)
        real = _service(session_scope, mailer, publisher, clock, test_mode=False)
        version = await _version(tester)
        await tester.send(_request(version))

        result = await real.send(_request(version, request_id="req-2"))

        assert result["status"] == "sent"


class TestHistoriaNaDesktop:
    async def test_tylko_wyslane_od_najnowszego(
        self, live: HubWholesaleService, mailer: FakeMailer, clock: Clock
    ):
        version = await _version(live)
        await live.send(_request(version))
        clock.now += timedelta(minutes=1)
        mailer.fail_with = MailSendError("x")
        await live.send(_request(version, request_id="req-bad", items=[1]))
        mailer.fail_with = None
        clock.now += timedelta(minutes=1)
        await live.send(_request(version, request_id="req-2", wholesaler_id="w-2", items=[0]))

        orders = await live.list_sent_orders(10)

        assert [o.request_id for o in orders] == ["req-2", "req-1"]
        assert orders[1].items_summary == "Kubek 300 ml x24, Miska x6"
