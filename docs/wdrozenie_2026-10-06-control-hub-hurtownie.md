# ORDLY — 6 października 2026: zamówienia w hurtowni z Control Hub

Nowy, szósty ekran Huba „Zamow w hurtowni” (między Historią a Statusem):
hurtownia -> szablon maila -> pozycje -> podgląd -> wysyłka po przytrzymaniu
OK przez 2 s. Mail składa ORDLY tymi samymi regułami co desktop
(`app/domain/wholesale_email.py` jest lustrem `wholesalerTemplate.ts`).

Hurtownie i szablony żyją na desktopie; desktop wysyła ich kopię na Pi
(`PUT /api/v1/hub/wholesale/catalog`) po zmianie, logowaniu i starcie.
Edycja zostaje na desktopie. Wysłane z Huba trafiają do historii na ekranie
Hurtownia (oznaczenie „Hub” / „Hub · test”).

**Zabezpieczenia:** adres tylko z kopii hurtowni, unikalny `request_id`
(brak podwójnej wysyłki), to samo zamówienie w 15 min wymaga potwierdzenia,
odrzucenie starej wersji katalogu. **Tryb testowy domyślnie WŁĄCZONY:** maile
z Huba idą na `SMTP_USER` z tematem `[TEST Hub -> <hurtownia>]`, nie do
hurtowni, dopóki w `.env` na Pi nie wpiszesz `HUB_WHOLESALE_TEST_MODE=false`.

**Migracja: TAK** (`0016 -> 0017`, tabele `hub_wholesale_catalog`,
`hub_wholesale_orders`). Nowe zależności: brak. Backend + desktop .exe +
firmware Huba (lokalny folder). PWA: nie.

## Kontrola (release manager)

- Merge `build/control-hub-hurtownie` (4ffafc9, 66b64dd): fast-forward na a1c6ad4, bez 42f9298.
- pytest 802 passed; ruff OK; mypy 35 znanych błędów; jeden head `0017`.
- Migracja na czystej bazie: upgrade, downgrade do 0016, upgrade OK.
- Desktop `npm run typecheck`: OK.
- Uwaga: test `test_dzisiejsza_sprzedaz_i_porownanie_z_wczoraj_o_tej_porze` może paść między 0:00 a 1:00 czasu polskiego (istniejący test, nie ta paczka); przeszedł o 1:53.
- Push: `a1c6ad4..66b64dd main -> main`. **Commit do rollbacku: `a1c6ad4`.**

## Rollback

`sudo systemctl stop ordly`, `cd ~/ordly/backend`, `uv run alembic downgrade 0016`
(usuwa tylko tabele hurtowni Huba), `git checkout a1c6ad4`, `uv sync`,
`sudo systemctl start ordly`, potem `git checkout main`. Desktop: poprzedni .exe
(z a1c6ad4). Hub: poprzednie firmware; bez backendu ekran pokaże błąd.
