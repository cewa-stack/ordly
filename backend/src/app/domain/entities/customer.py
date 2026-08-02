"""Encja domenowa reprezentująca kupującego, niezależna od marketplace."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Customer:
    """
    Kupujący w ujęciu biznesowym.

    Immutable (frozen) - kupujący raz pobrany w ramach zamówienia
    nie powinien być mutowany; ewentualna aktualizacja danych
    tworzy nową instancję.
    """

    login: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
