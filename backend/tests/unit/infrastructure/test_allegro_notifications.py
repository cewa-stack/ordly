"""
Testy odczytu powiadomień e-mail z Allegro.pl.

Działają na PRAWDZIWYCH mailach (`tests/fixtures/allegro_mail/`).
Sprawdzają dwie rzeczy naraz: że mail o nowej dyskusji daje komplet
danych do powiadomienia ORAZ że mail o zwrocie NIE daje nic - bo o zwrocie
ORDLY wie już z API i drugie powiadomienie byłoby duplikatem.
"""

from __future__ import annotations

import pathlib
from datetime import datetime
from email import message_from_bytes

from app.domain.entities.mail_message import MailMessage
from app.infrastructure.mail.allegro_notifications import parse_dispute_notice
from app.infrastructure.mail.imap_watcher import _parse_message
from app.infrastructure.mail.mime import MailBodies, extract_bodies

FIXTURES = pathlib.Path(__file__).parents[2] / "fixtures" / "allegro_mail"
DYSKUSJA = "dyskusja-rozpoczeta.eml"
ZWROT = "zwrot-odstapienie.eml"


def wczytaj(nazwa: str) -> tuple[MailMessage, MailBodies]:
    raw = (FIXTURES / nazwa).read_bytes()
    message = _parse_message(raw)
    assert message is not None
    return message, extract_bodies(message_from_bytes(raw))


class TestKopertaISkrzynka:
    """Zanim dojdzie do rozpoznawania zdarzeń - jak te maile widzi skrzynka."""

    def test_powiadomienia_z_allegro_pl_to_kanal_allegro(self):
        """
        Regresja granicy między kanałami: `powiadomienia@allegro.pl`
        zawiera podciąg "allegro", ale NIE "allegrolokalnie" - musi
        trafić do Allegro.pl, inaczej wpadłby w tor Allegro Lokalnie.
        """
        for nazwa in (DYSKUSJA, ZWROT):
            message, _ = wczytaj(nazwa)
            assert message.source == "allegro", nazwa

    def test_podglad_nie_zawiera_surowego_html(self):
        """Oba maile są jednoczęściowe `text/html`, jak te z Lokalnie."""
        for nazwa in (DYSKUSJA, ZWROT):
            message, _ = wczytaj(nazwa)
            assert "<" not in message.body_preview, nazwa
            assert "DOCTYPE" not in message.body_preview, nazwa

    def test_temat_zwrotu_nie_jest_zlamany(self):
        """Temat zwrotu ma dwa kodowane fragmenty i łamie się na dwie linie."""
        message, _ = wczytaj(ZWROT)

        assert "\n" not in message.subject
        assert message.subject.endswith("Zwrot nr: 7165/2026")


class TestNowaDyskusja:
    """Jedyne zdarzenie, które ORDLY czyta z poczty Allegro.pl."""

    def test_rozpoznaje_mail_o_rozpoczeciu_dyskusji(self):
        message, bodies = wczytaj(DYSKUSJA)

        notice = parse_dispute_notice(message, bodies)

        assert notice is not None
        assert notice.buyer_login == "Rexpiot"

    def test_prowadzi_do_konkretnego_watku(self):
        """
        Identyfikator z linku „Przejdź do dyskusji" jest tym samym, którego
        używa `/api/v1/issues/{id}/messages` - dzięki temu kliknięcie
        w powiadomienie otwiera wątek, a nie listę.
        """
        message, bodies = wczytaj(DYSKUSJA)

        notice = parse_dispute_notice(message, bodies)

        assert notice is not None
        assert notice.issue_id == "81ecd951-ab12-4528-8154-af5699df2b1c"

    def test_niesie_termin_odpowiedzi_ktorego_nie_ma_w_api(self):
        """
        „Jeśli nie wypowiesz się do 29.07.2026 08:41, włączymy się do
        rozmowy" - ten termin jest WYŁĄCZNIE w mailu i to on decyduje
        o pilności.
        """
        message, bodies = wczytaj(DYSKUSJA)

        notice = parse_dispute_notice(message, bodies)

        assert notice is not None
        assert notice.respond_by == datetime(2026, 7, 29, 8, 41)

    def test_niesie_powod_zamowienie_i_oferte(self):
        message, bodies = wczytaj(DYSKUSJA)

        notice = parse_dispute_notice(message, bodies)

        assert notice is not None
        assert notice.reason == "niezgodny z opisem"
        assert notice.order_external_id == "deeb2fc0-8419-11f1-bed3-7de93eca4a57"
        assert notice.offer_name == (
            "50x Butelki PET 30ml z zakrętką+kroplomierz do liquidów olejek kosmetyków"
        )


class TestCzegoNieCzytamy:
    """
    Granica podziału pracy między API a pocztą. Allegro.pl ma API i ORDLY
    z niego korzysta - poczta ma dokładać TYLKO to, czego API nie daje.
    """

    def test_mail_o_zwrocie_nie_generuje_zdarzenia(self):
        """
        Zwroty pobiera `SyncOrdersService._sync_customer_returns` z API
        i publikuje `OrderReturnCreated`, które już powiadamia. Drugi tor
        z poczty dałby dwa powiadomienia o jednym zwrocie.
        """
        message, bodies = wczytaj(ZWROT)

        assert parse_dispute_notice(message, bodies) is None

    def test_mail_bez_zdania_o_rozpoczeciu_dyskusji_nie_liczy_sie(self):
        """
        Allegro używa słowa „Dyskusja" także w mailach o kolejnych
        wiadomościach w trwającym wątku - te nie są nowym zdarzeniem.
        """
        message, _ = wczytaj(DYSKUSJA)
        inny = MailMessage(
            message_id=message.message_id,
            sender=message.sender,
            subject="Dyskusja - nowa wiadomość od naszego doradcy",
            received_at=message.received_at,
            source=message.source,
            body_preview="Masz nową wiadomość w dyskusji.",
        )

        assert parse_dispute_notice(inny) is None

    def test_bez_pelnej_tresci_nie_zgaduje(self):
        """
        Identyfikator wątku jest tylko w HTML-u. Gdy dociągnięcie treści
        zawiedzie, lepiej nie powiadamiać niż powiadomić bez miejsca,
        do którego można przejść.
        """
        message, _ = wczytaj(DYSKUSJA)

        assert parse_dispute_notice(message) is None
