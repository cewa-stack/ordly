"""Klasyfikacja nadawcy maila na kanał sprzedaży (Allegro/Allegro Lokalnie/OLX/inny)."""

from __future__ import annotations

#: Kanał Allegro Lokalnie - osobny od Allegro.pl, bo to inny serwis
#: z innym zakresem możliwości: nie ma publicznego API (Allegro
#: potwierdziło, że nie planuje go udostępnić), więc ORDLY zna stamtąd
#: wyłącznie to, co przyjdzie mailem, i nie potrafi tam niczego zmienić.
#: Mieszanie obu kanałów pod jedną etykietą sugerowałoby, że zamówieniem
#: z Lokalnie da się zarządzać z aplikacji tak samo jak z Allegro.pl.
SOURCE_ALLEGRO_LOKALNIE = "allegro_lokalnie"
SOURCE_ALLEGRO = "allegro"
SOURCE_OLX = "olx"
SOURCE_OTHER = "other"


def classify_sender(sender: str) -> str:
    """
    Rozpoznaje kanał po adresie/domenie nadawcy.

    Proste dopasowanie podciągu wystarcza - realne adresy nadawców
    (np. noreply@allegromail.pl, powiadomienia@allegrolokalnie.pl,
    noreply@olx.pl) zawierają nazwę serwisu w domenie.

    KOLEJNOŚĆ WARUNKÓW MA ZNACZENIE: `allegrolokalnie.pl` zawiera
    podciąg "allegro", więc sprawdzenie Allegro.pl jako pierwsze
    zagarniałoby wszystkie powiadomienia z Lokalnie pod niewłaściwą
    etykietę - i tak było, zanim powstał osobny kanał.
    """
    sender_lower = sender.lower()
    if "allegrolokalnie" in sender_lower:
        return SOURCE_ALLEGRO_LOKALNIE
    if "allegro" in sender_lower:
        return SOURCE_ALLEGRO
    if "olx" in sender_lower:
        return SOURCE_OLX
    return SOURCE_OTHER
