"""
Testy rozbierania wiadomości MIME na część HTML i tekstową.

Regresja buga "w zakładce Wiadomość widać surowy kod HTML": poprzedni
kod brał payload całej wiadomości i traktował go jak tekst, więc dla
maila jednoczęściowego `text/html` (tak wysyła Allegro) na ekran szło
`<!DOCTYPE HTML ...` zamiast treści.
"""

from __future__ import annotations

from email import message_from_bytes
from email.message import EmailMessage

from app.infrastructure.mail.mime import extract_bodies, html_to_plain_text

# Skrót realnego powiadomienia Allegro ze zgłoszenia: pełny dokument HTML
# z DOCTYPE, nagłówkiem, stylami i encjami.
_ALLEGRO_HTML = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html lang="pl" xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <meta http-equiv="Content-Type" content="text/html charset=UTF-8" />
    <style type="text/css">
      body { margin: 0; font-family: Arial, sans-serif; }
      .cta { background:#ff5a00; }
    </style>
  </head>
  <body>
    <p>Dzie&#324; dobry,</p>
    <p>masz now&#261; wiadomo&#347;&#263; od naszego doradcy w sprawie
       dyskusji do zam&oacute;wienia.</p>
    <p><a href="https://allegro.pl/moje-allegro/dyskusje">Przejd&#378; do dyskusji</a></p>
  </body>
</html>"""


def _multipart_mail() -> EmailMessage:
    message = EmailMessage()
    message["From"] = "Allegro <powiadomienia@allegro.pl>"
    message["Subject"] = "Dyskusja - nowa wiadomość od naszego doradcy"
    message.set_content("Dzień dobry,\n\nmasz nową wiadomość od naszego doradcy.")
    message.add_alternative(_ALLEGRO_HTML, subtype="html")
    return message


class TestExtractBodies:
    def test_multipart_daje_obie_wersje_osobno(self):
        bodies = extract_bodies(_multipart_mail())

        assert bodies.text is not None
        assert "masz nową wiadomość" in bodies.text
        assert bodies.html is not None
        assert bodies.html.startswith("<!DOCTYPE HTML")

    def test_mail_tylko_html_zwraca_html_bez_tekstu(self):
        """
        Ten przypadek generował buga: mail jednoczęściowy `text/html`
        nie ma części `text/plain`, więc poprzedni kod oddawał surowe
        źródło jako "treść tekstową".
        """
        message = EmailMessage()
        message["From"] = "Allegro <powiadomienia@allegro.pl>"
        message.set_content(_ALLEGRO_HTML, subtype="html")

        bodies = extract_bodies(message)

        assert bodies.text is None
        assert bodies.html is not None
        assert "Przejd" in bodies.html

    def test_mail_tylko_tekstowy_zwraca_tekst_bez_html(self):
        message = EmailMessage()
        message["From"] = "OLX <noreply@olx.pl>"
        message.set_content("Masz nową wiadomość od kupującego.")

        bodies = extract_bodies(message)

        assert bodies.html is None
        assert bodies.text is not None
        assert "kupującego" in bodies.text

    def test_zalacznik_html_nie_podszywa_sie_pod_tresc(self):
        """Doklejony plik `.html` nie jest treścią maila i nie może jej przesłonić."""
        message = EmailMessage()
        message["From"] = "Allegro <powiadomienia@allegro.pl>"
        message.set_content("Faktura w załączniku.")
        message.add_attachment(
            b"<html><body>FAKTURA</body></html>",
            maintype="text",
            subtype="html",
            filename="faktura.html",
        )

        bodies = extract_bodies(message)

        assert bodies.html is None
        assert bodies.text is not None
        assert "Faktura w załączniku" in bodies.text

    def test_quoted_printable_i_polskie_znaki(self):
        """Treść zakodowana quoted-printable musi wrócić zdekodowana."""
        raw = (
            b"From: Allegro <powiadomienia@allegro.pl>\r\n"
            b"Content-Type: text/plain; charset=UTF-8\r\n"
            b"Content-Transfer-Encoding: quoted-printable\r\n"
            b"\r\n"
            b"Zam=C3=B3wienie zosta=C5=82o op=C5=82acone.\r\n"
        )

        bodies = extract_bodies(message_from_bytes(raw))

        assert bodies.text is not None
        assert "Zamówienie zostało opłacone." in bodies.text

    def test_nieznane_kodowanie_nie_wywala_odczytu(self):
        """Literówka w nazwie charsetu ma zejść na UTF-8, a nie rzucić LookupError."""
        raw = (
            b"From: Allegro <powiadomienia@allegro.pl>\r\n"
            b'Content-Type: text/plain; charset="utf8-nieistniejacy"\r\n'
            b"\r\n"
            b"Tresc maila\r\n"
        )

        bodies = extract_bodies(message_from_bytes(raw))

        assert bodies.text is not None
        assert "Tresc maila" in bodies.text


class TestHtmlToPlainText:
    def test_usuwa_znaczniki_style_i_doctype(self):
        text = html_to_plain_text(_ALLEGRO_HTML)

        assert "<" not in text
        assert "DOCTYPE" not in text
        assert "font-family" not in text, "styl CSS nie może wyciec do treści"

    def test_dekoduje_encje(self):
        text = html_to_plain_text(_ALLEGRO_HTML)

        assert "Dzień dobry," in text
        assert "zamówienia" in text
        assert "Przejdź do dyskusji" in text

    def test_br_i_akapity_daja_zlamania_linii(self):
        text = html_to_plain_text("<p>Pierwszy</p><p>Drugi<br>Trzeci</p>")

        assert text == "Pierwszy\n\nDrugi\nTrzeci"

    def test_skrypt_nie_trafia_do_tresci(self):
        text = html_to_plain_text("<p>przed</p><script>alert(1)</script><p>po</p>")

        assert "alert" not in text
        assert "przed" in text and "po" in text

    def test_komentarz_warunkowy_outlooka_znika(self):
        """Szablony maili obudowują bloki `<!--[if mso]>...<![endif]-->`."""
        text = html_to_plain_text("<p>tresc</p><!--[if mso]><table><tr><td>x<![endif]-->")

        assert text == "tresc"
