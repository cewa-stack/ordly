# APPPLANS 02 — Sync Engine (auto-synchronizacja co 60s) + WebSocket Hub

> Zależności: `appplans_00_overview.md` (przeczytane, fundament zaakceptowany).
> To jest moduł bazowy — wdrażany jako pierwszy z modułów funkcjonalnych.

## 1. Cel

Jeden centralny job w Comcio (RPi), uruchamiany co 60 sekund przez APScheduler, który:
1. Odpytuje Allegro API (oferty, zamówienia, zwroty, dyskusje — zakres wg dostępnych scope'ów).
2. Wykrywa zmiany względem poprzedniego stanu (diff, nie brute-force overwrite).
3. Zapisuje zmiany do SQLite.
4. Emituje eventy przez WebSocket do wszystkich podłączonych klientów (desktop + mobile).
5. Wysyła push (FCM) do mobile, jeśli event wymaga natychmiastowej uwagi.

## 2. Krok 0 — Alembic (jeśli brak)

Jeśli projekt Comcio nie ma jeszcze migracji wersjonowanych:
```bash
uv add alembic
alembic init migrations
```
Skonfigurować `env.py` żeby czytał `Base.metadata` z istniejących modeli SQLAlchemy. Zrobić
pierwszą migrację "baseline" ze snapshotem obecnego schematu, zanim dodamy nowe tabele.

## 3. Nowe tabele SQLite (przez Alembic)

```python
# app/models/sync.py
class SyncState(Base):
    __tablename__ = "sync_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_type: Mapped[str]  # "offers" | "orders" | "returns" | "disputes" | "olx_offers"
    last_synced_at: Mapped[datetime]
    last_payload_hash: Mapped[str]  # sha256 do szybkiego diffu bez porównywania pól po polu
    consecutive_errors: Mapped[int] = mapped_column(default=0)

class NotificationLog(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str]
    payload_json: Mapped[str]
    created_at: Mapped[datetime]
    delivered_desktop: Mapped[bool] = mapped_column(default=False)
    delivered_mobile: Mapped[bool] = mapped_column(default=False)
    read_at: Mapped[datetime | None]
```

## 4. Scheduler job

```python
# app/services/sync_scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Europe/Warsaw")

@scheduler.scheduled_job("interval", seconds=60, id="main_sync", max_instances=1)
async def run_sync_cycle():
    """max_instances=1 jest krytyczne — jeśli poprzedni cykl się nie skończył
    (np. Allegro odpowiada wolno), NIE odpalamy kolejnego równolegle."""
    for plugin in registered_plugins:  # allegro, olx (po appplans_05), ...
        try:
            changes = await plugin.sync()
            for change in changes:
                await persist_change(change)
                await event_bus.publish(change.to_event())
        except PluginRateLimitError:
            logger.warning(f"{plugin.name}: rate limited, backing off")
            await bump_backoff(plugin.name)
        except Exception:
            logger.exception(f"{plugin.name}: sync cycle failed")
```

**Ważne szczegóły:**
- Każdy plugin implementuje `sync() -> list[Change]`, zwraca TYLKO różnice (nie cały stan).
- Backoff: jeśli plugin dostanie rate-limit (429) lub 3x błąd z rzędu, następny sync tego
  pluginu przesuwany jest o dodatkowe 60s (nie blokuje innych pluginów).
- Cały cykl ma timeout 45s (przed kolejnym tickiem 60s) — użyć `asyncio.wait_for` per plugin,
  żeby jeden zawieszony plugin nie zablokował reszty.

## 5. WebSocket Hub

```python
# app/api/ws.py
from fastapi import WebSocket

class EventBus:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket, client_id: str):
        await ws.accept()
        self._connections.add(ws)

    async def publish(self, event: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

event_bus = EventBus()

@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket, token: str = Query(...)):
    if not await verify_device_token(token):
        await websocket.close(code=4401)
        return
    await event_bus.connect(websocket, token)
    try:
        while True:
            await websocket.receive_text()  # keep-alive ping z klienta
    except WebSocketDisconnect:
        event_bus.disconnect(websocket)
```

Format eventu (kontrakt z klientami — desktop i mobile muszą go respektować):
```json
{
  "type": "stock_changed",
  "resource_id": "offer_12345",
  "data": { "sku": "ABC-123", "stock_before": 5, "stock_after": 0 },
  "timestamp": "2026-07-30T10:00:00Z",
  "severity": "warning"
}
```
Typy eventów na start: `stock_changed`, `new_order`, `return_opened`, `dispute_opened`,
`cancellation`, `new_mail`, `sync_error`.

## 6. Strona Electron (desktop) — konsument

```typescript
// src/services/comcioClient.ts
class ComcioClient {
  private ws: WebSocket | null = null;

  connect(baseUrl: string, token: string) {
    this.ws = new WebSocket(`${baseUrl.replace('http', 'ws')}/ws/events?token=${token}`);
    this.ws.onmessage = (msg) => {
      const event: ComcioEvent = JSON.parse(msg.data);
      eventEmitter.emit(event.type, event);
    };
    this.ws.onclose = () => setTimeout(() => this.connect(baseUrl, token), 5000); // reconnect
  }
}
```
**Uwaga bezpieczeństwa**: WebSocket łączy się z main procesem Electron (nie z rendera
bezpośrednio), analogicznie do wzorca z `allegroAuth.js` — token Comcio nigdy nie trafia do
warstwy renderera w czystej postaci, przechodzi przez `contextBridge` jako opakowana metoda
`window.comcio.onEvent(callback)`.

## 7. Parowanie urządzeń (device pairing)

1. Przy pierwszym starcie Comcio generuje losowy `device_pairing_secret` i wystawia go jako
   QR code pod `GET /pair/qr` (renderowany jako obrazek PNG z biblioteki `qrcode`).
2. Desktop app przy pierwszym uruchomieniu pokazuje ekran "zeskanuj QR" — ale desktop nie ma
   kamery, więc desktop paruje się przez wpisanie adresu IP RPi + kodu wyświetlonego na
   ekranie/terminalu Comcio (6-cyfrowy PIN, ważny 5 minut).
3. Mobile app paruje się przez skan QR z ekranu Comcio (lub z desktopu, jeśli desktop
   wyświetli ten sam QR w swoim UI).
4. Po sparowaniu, Comcio wydaje długoterminowy JWT (podpisany kluczem z `.env`,
   `COMCIO_JWT_SECRET`), zapisywany lokalnie po stronie klienta (Electron: `electron-store`
   zaszyfrowany; Mobile: `expo-secure-store`).

## 8. Testy wymagane

- Unit: `sync_cycle` z mockowanym pluginem zwracającym zmiany — sprawdzić że event trafia do
  `event_bus.publish` dokładnie raz.
- Unit: backoff — 3 błędy z rzędu → `consecutive_errors == 3` → kolejny sync opóźniony.
- Integration: WebSocket — klient łączy się z nieprawidłowym tokenem → connection closed
  z kodem 4401.
- Manualny test: wyłączyć wifi na 2 minuty w trakcie działania — sprawdzić że reconnect
  działa i nie ma duplikatów eventów po powrocie.

## 9. Definition of Done

- [ ] Alembic skonfigurowany, migracja baseline + migracja nowych tabel.
- [ ] `run_sync_cycle` działa co 60s, widoczne w logach Loguru z timestampem każdego cyklu.
- [ ] WebSocket hub odrzuca połączenia bez ważnego tokenu.
- [ ] Desktop app łączy się, odbiera event testowy (endpoint `/debug/emit-test-event`) i
      wyświetla go w UI (np. toast).
- [ ] Rate-limit na Allegro nie powoduje crasha ani zawieszenia całego cyklu.
- [ ] Dokumentacja kontraktu eventów zaktualizowana w `AGENT.md`.
