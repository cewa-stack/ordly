"""Encja domenowa powiadomienia o rozpoczętej dyskusji na Allegro.pl."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DisputeNotice:
    """
    Informacja, że kupujący właśnie rozpoczął dyskusję - odczytana
    z maila powiadamiającego od Allegro.

    Po co mail, skoro Allegro.pl MA API: bo ORDLY odpytuje `/sale/issues`
    wyłącznie na żądanie (gdy otwierasz ekran Dyskusji), więc o nowej
    dyskusji dowiadywałeś się dopiero wtedy, gdy sam zajrzałeś. Mail
    przychodzi natychmiast.

    Drugi powód jest mocniejszy: `respond_by` NIE MA w API. Allegro pisze
    w mailu „Jeśli nie wypowiesz się do 29.07.2026 08:41, włączymy się do
    rozmowy" - i to jest jedyne miejsce, w którym ten termin się pojawia.
    A to on decyduje o pilności.

    Encja NIE zastępuje `Issue` z API - tamta ma pełny wątek wiadomości
    i status. Ta niesie tylko tyle, ile trzeba, żeby powiadomić i wskazać
    właściwą dyskusję.
    """

    message_id: str
    #: Identyfikator dyskusji z linku „Przejdź do dyskusji" - ten sam,
    #: którym posługuje się `/api/v1/issues/{id}/messages`, więc
    #: powiadomienie prowadzi wprost do wątku.
    issue_id: str
    buyer_login: str
    received_at: datetime
    #: Numer zamówienia, którego dotyczy dyskusja.
    order_external_id: str | None = None
    #: Nazwa oferty, np. "50x Butelki PET 30ml z zakrętką+kroplomierz…".
    offer_name: str | None = None
    #: Powód zgłoszony przez kupującego, np. "niezgodny z opisem".
    reason: str | None = None
    #: Termin, do którego trzeba odpowiedzieć, zanim Allegro dołączy do
    #: rozmowy. `None`, gdy szablon maila go nie zawierał.
    respond_by: datetime | None = None
