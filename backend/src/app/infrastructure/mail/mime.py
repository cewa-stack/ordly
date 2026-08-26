"""
Wyciąganie treści z wiadomości MIME - osobno wersja HTML i tekstowa.

Wcześniej skrzynka brała `msg.get_payload()` całej wiadomości i wrzucała
wynik na ekran jako tekst. Dla maila jednoczęściowego `text/html` (a takie
wysyła Allegro) oznaczało to, że użytkownik widział `<!DOCTYPE HTML ...`,
`<head>`, style - czyli źródło zamiast wiadomości. Tutaj wiadomość jest
rozbierana na części tak, jak robi to każdy klient pocztowy: aplikacja
dostaje `html` do wyrenderowania i `text` jako zapasowy, czytelny wariant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.message import Message
from html import unescape

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# `.*?` z DOTALL, bo blok stylu maila potrafi mieć kilkadziesiąt linii.
_SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
# Akapit i nagłówek konczą się PUSTĄ linią, reszta bloków zwykłym
# złamaniem - ta sama zasada co w rendererach po stronie aplikacji
# (`desktop/.../sanitizeHtml.ts`, `mobile/src/utils/html.ts`).
_PARAGRAPH_END = re.compile(r"</(p|h[1-6]|blockquote)\s*>", re.IGNORECASE)
_BLOCK_END = re.compile(r"</(div|tr|li|ul|ol|table|section|article)\s*>", re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")
_SPACES_NO_NEWLINE = re.compile(r"[^\S\n]+")
_MANY_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True, slots=True)
class MailBodies:
    """
    Treść maila w obu wariantach, tak jak leżą w wiadomości MIME.

    `html` renderuje aplikacja (desktop w `<iframe>`, PWA w `<iframe>`),
    `text` jest wariantem zapasowym - używanym, gdy mail nie ma części
    HTML albo gdy widok nie potrafi jej pokazać. Oba mogą być `None`
    (mail bez czytelnej treści, np. sam załącznik) - to normalny stan,
    nie błąd.
    """

    html: str | None
    text: str | None


def extract_bodies(message: Message) -> MailBodies:
    """
    Wyciąga pierwszą część `text/html` i pierwszą `text/plain`.

    `walk()` obsługuje jednakowo mail jednoczęściowy (zwraca sam siebie)
    i zagnieżdżony `multipart/mixed` -> `multipart/alternative`, więc nie
    ma tu osobnej gałęzi na `is_multipart()` - jedna ścieżka, mniej miejsc
    na rozjazd.

    Załączniki są pomijane: plik `.txt` czy `.html` doklejony do maila
    nie jest jego treścią, a bez tego filtra potrafiłby ją przesłonić.
    """
    html: str | None = None
    text: str | None = None

    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if _is_attachment(part):
            continue
        content_type = part.get_content_type()
        if content_type == "text/html" and html is None:
            html = _decode_part(part)
        elif content_type == "text/plain" and text is None:
            text = _decode_part(part)

    return MailBodies(html=html, text=text)


def html_to_plain_text(html: str) -> str:
    """
    Zamienia HTML maila na czytelny tekst - do podglądu na liście i do
    wariantu zapasowego, gdy widok nie renderuje HTML-a.

    Świadomie bez `beautifulsoup4`: to nowa zależność na Pi, a zadanie
    sprowadza się do wycięcia znaczników i zamiany kilku z nich na
    złamania linii. Wynik nie musi być wierny - ma być czytelny i nie
    zawierać nawiasów kątowych.
    """
    without_comments = _COMMENT.sub(" ", html)
    without_code = _SCRIPT_OR_STYLE.sub(" ", without_comments)
    with_breaks = _LINE_BREAK.sub("\n", without_code)
    with_breaks = _PARAGRAPH_END.sub("\n\n", with_breaks)
    with_breaks = _BLOCK_END.sub("\n", with_breaks)
    stripped = _ANY_TAG.sub("", with_breaks)

    # `unescape` ze stdlib zna pełną tabelę encji HTML5 - własna mapa
    # zawsze byłaby niepełna przy pierwszym nietypowym szablonie.
    lines = [
        _SPACES_NO_NEWLINE.sub(" ", line).strip() for line in unescape(stripped).split("\n")
    ]
    return _MANY_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def _is_attachment(part: Message) -> bool:
    """Załącznik rozpoznajemy po dyspozycji ALBO po nazwie pliku (starsze klienty)."""
    return part.get_content_disposition() == "attachment" or bool(part.get_filename())


def _decode_part(part: Message) -> str | None:
    """
    Dekoduje jedną część wiadomości na tekst.

    Kodowanie deklarowane przez nadawcę bywa nieznane Pythonowi
    (np. literówka w nazwie zestawu znaków) - `LookupError` nie może
    wtedy wywalić całego odczytu maila, więc schodzimy na UTF-8.
    """
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes):
        return None
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")
