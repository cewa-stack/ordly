"""Encje domenowe zapisanej rozmowy z asystentem Ordlaka."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

ChatRole = Literal["user", "assistant"]

#: Ile znaków pierwszego pytania trafia do tytułu wątku na liście rozmów.
TITLE_MAX_LENGTH = 60


@dataclass(frozen=True, slots=True)
class OrdlakMessage:
    """
    Jedna wypowiedź w zapisanej rozmowie.

    `used_tools` przechowujemy razem z odpowiedzią, a nie liczymy na nowo:
    to ślad po TYM konkretnym raporcie. Gdyby wyliczać go później, wracając
    do wątku sprzed tygodnia widziałoby się narzędzia dzisiejszego kodu,
    a nie te, które faktycznie dały tamte liczby.
    """

    id: int | None
    role: ChatRole
    content: str
    created_at: datetime
    used_tools: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OrdlakConversation:
    """
    Wątek rozmowy z asystentem.

    `title` powstaje z pierwszego pytania użytkownika - lista rozmów ma
    dać się przeglądać wzrokiem, a "Rozmowa #7" nic nie mówi.
    """

    id: int | None
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    messages: tuple[OrdlakMessage, ...] = field(default=())


def title_from_question(question: str) -> str:
    """
    Buduje tytuł wątku z pierwszego pytania - jedna linia, przycięta.

    Nowe linie znikają, bo tytuł jest jednowierszowy na liście; pusty
    tekst nie ma prawa tu trafić (endpoint wymaga treści), ale gdyby
    trafił, lepszy zapasowy tytuł niż pusty wiersz.
    """
    single_line = " ".join(question.split())
    if not single_line:
        return "Rozmowa bez tytułu"
    if len(single_line) <= TITLE_MAX_LENGTH:
        return single_line
    return single_line[: TITLE_MAX_LENGTH - 1].rstrip() + "…"
