"""Klasyfikacja nadawcy maila na marketplace (Allegro/OLX/inny)."""

from __future__ import annotations


def classify_sender(sender: str) -> str:
    """
    Rozpoznaje marketplace po adresie/domenie nadawcy.

    Proste dopasowanie podciągu wystarcza - realne adresy nadawców
    (np. noreply@allegromail.pl, noreply@olx.pl) zawierają nazwę
    marketplace w domenie.
    """
    sender_lower = sender.lower()
    if "allegro" in sender_lower:
        return "allegro"
    if "olx" in sender_lower:
        return "olx"
    return "other"
