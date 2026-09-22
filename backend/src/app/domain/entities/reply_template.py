"""Encja domenowa - gotowa odpowiedź do dyskusji z kupującym."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReplyTemplate:
    """
    Szablon odpowiedzi wstawiany do pola odpowiedzi w Dyskusjach.

    Treść może zawierać znaczniki `{login}`, `{numer_zamowienia}` i
    `{numer_przesylki}`. Serwer ich NIE podstawia - robi to aplikacja,
    która ma pod ręką wątek i zamówienie. Dzięki temu ten sam szablon
    działa tak samo na desktopie i na telefonie, a człowiek widzi gotowy
    tekst przed wysłaniem.
    """

    id: int
    title: str
    body: str
    position: int
