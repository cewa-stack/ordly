"""
Generuje parę kluczy VAPID do Web Push i wypisuje ją w formacie gotowym
do wklejenia w `.env`.

Dlaczego osobny skrypt, a nie komentarz w `.env.example`: dotychczas była
tam wieloliniowa komenda `uv run python -c "..."`, której nie da się
skopiować jednym ruchem do terminala przez SSH - łamie się na cudzysłowach
i wcięciach. Konfiguracja powiadomień to rzecz robiona raz, pod presją,
na cudzym sprzęcie; ma być jedno polecenie.

Użycie na Raspberry Pi:

    cd ~/ordly/backend && uv run python scripts/generate_vapid_keys.py

Klucze są zapisywane WYŁĄCZNIE na ekran - skrypt świadomie nie dotyka
`.env`, żeby nie nadpisać działającej konfiguracji. Podmiana kluczy
unieważnia wszystkie istniejące subskrypcje: każdy telefon musi wtedy
włączyć powiadomienia od nowa.
"""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid02


def _b64url(raw: bytes) -> str:
    """Base64url bez dopełnienia - format wymagany przez specyfikację VAPID."""
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def main() -> None:
    """Wypisuje trzy linie do wklejenia w `.env`."""
    vapid = Vapid02()
    vapid.generate_keys()

    if vapid.private_key is None or vapid.public_key is None:
        raise RuntimeError("Nie udało się wygenerować pary kluczy VAPID.")

    private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)

    print("# Wklej poniższe trzy linie do ~/ordly/backend/.env,")
    print("# podmieniając istniejące wpisy VAPID_*, a potem:")
    print("#   sudo systemctl restart ordly")
    print()
    print(f"VAPID_PUBLIC_KEY={_b64url(public_raw)}")
    print(f"VAPID_PRIVATE_KEY={_b64url(private_raw)}")
    print("VAPID_CLAIM_EMAIL=mailto:admin@example.com")
    print()
    print("# UWAGA: podmiana kluczy unieważnia wszystkie zapisane subskrypcje -")
    print("# na każdym telefonie trzeba będzie włączyć powiadomienia ponownie.")


if __name__ == "__main__":
    main()
