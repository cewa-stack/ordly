# ORDLY — 4 października 2026: most MQTT do Control Hub (etap 4)

Backend ORDLY rozmawia z ORDLy Control Hub (ESP32) przez broker Mosquitto
na Pi (zainstalowany w etapie 3 budowy Huba).

**Co zmienia ta paczka (tylko backend na Pi):**

1. Nowe zamówienie / zwrot / dyskusja / wiadomość Allegro Lokalnie i OLX /
   problem z systemem -> wiadomość `ordly/events/new`.
2. Zamówienie spakowane, anulowane lub nadane, zamknięty zwrot, kanał znów
   działa -> `ordly/events/resolved`.
3. Przycisk OK na Hubie (`ordly/hub/ack`) zamyka zdarzenie w bazie i
   zapisuje `HubEventAcknowledged` w audycie.
4. Hub po połączeniu dostaje snapshot aktywnych zdarzeń, statystyki dnia i
   stan systemu; co 60 s odświeżenie z godziną.
5. ORDLY ogłasza się na `ordly/backend/status` (retained + LWT).

Protokół: `backend/docs/control_hub_mqtt.md`.

**Migracja: TAK** (`0013 -> 0014`, nowa tabela `hub_events`).
**Nowa zależność:** `aiomqtt` (+ `paho-mqtt`) przez `uv sync`.
**Nowa zmienna `.env`:** `MQTT_PASSWORD` (bez niej most jest wyłączony).
**PWA / desktop:** bez zmian.

## Kontrola przed wdrożeniem (release manager)

- Merge `build/control-hub-mqtt` (`691fa02`) do `main`: fast-forward.
- `pytest`: 666 passed; `ruff`: OK; jeden head Alembic `0014`.
- Test migracji na czystej bazie: `0012 -> 0013 -> 0014` OK.
- Uwaga środowiskowa: lokalnie komendy `uv run pytest` / `uv run alembic`
  milczą z exit 1 — działa `uv run python -m pytest` / `-m alembic`.
- Push: `c653e28..691fa02 main -> main`.
- **Commit do rollbacku: `c653e28`.**

## Rollback

Wystarczy wyczyścić `MQTT_PASSWORD` w `.env` i zrestartować usługę — most
się wyłącza. Pełny: `sudo systemctl stop ordly`, `cd ~/ordly/backend`,
`uv run alembic downgrade 0013` (usuwa tylko `hub_events`),
`git checkout c653e28`, `uv sync`, `sudo systemctl start ordly`; potem
`git checkout main`.
