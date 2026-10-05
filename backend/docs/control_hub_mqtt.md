# ORDLy Control Hub — most MQTT

Control Hub to konsola na ESP32 (ekran 480×320, 4 przyciski, 4 diody), która pokazuje zdarzenia z ORDLY. Hub niczego nie liczy i nie łączy się z internetem: wszystko, także godzinę, dostaje od ORDLY przez broker Mosquitto na tym samym Raspberry Pi.

## Włączenie

W `.env` na Pi:

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `MQTT_HOST` | `localhost` | broker na tym samym Pi |
| `MQTT_PORT` | `1883` | |
| `MQTT_USER` | `ordly` | użytkownik z `/etc/mosquitto/passwd` |
| `MQTT_PASSWORD` | puste | **puste = most wyłączony**, ORDLY działa jak dotąd |
| `HUB_PUBLISH_INTERVAL_SECONDS` | `60` | co ile stan systemu i statystyki |

Bez brokera albo przy złym haśle ORDLY działa normalnie: most co 5–60 s próbuje się połączyć i pisze ostrzeżenie w logu.

## Tematy

| Temat | Kierunek | Retained | Treść |
|---|---|---|---|
| `ordly/events/new` | ORDLY → Hub | nie | `{id, type, priority, ts, data}` — nowe zdarzenie |
| `ordly/events/resolved` | ORDLY → Hub | nie | `{event_id, reason}` — sprawa zamknięta w ORDLY |
| `ordly/events/snapshot` | ORDLY → Hub | nie | `{events: [...], total, ts}` — komplet aktywnych (max 20), po każdym „online” Huba |
| `ordly/stats/today` | ORDLY → Hub | tak | `{revenue, orders, avg_order, vs_yesterday_pct, ts}` |
| `ordly/system/status` | ORDLY → Hub | tak | `{ts, last_sync_at, problems}` — `ts` to zegar Huba |
| `ordly/backend/status` | ORDLY → Hub | tak, LWT | `{online}` — Hub miga niebieską, gdy ORDLY nie działa |
| `ordly/hub/status` | Hub → ORDLY | tak, LWT | `{online, fw_version, etap, ip, rssi, uptime_s}` |
| `ordly/hub/ack` | Hub → ORDLY | nie | `{event_id, action: "acknowledged"}` — przycisk OK |
| `ordly/hub/history/get` | Hub → ORDLY | nie | `{date?: "RRRR-MM-DD", page?: 0}` — prośba o ekran historii (brak daty = dziś) |
| `ordly/history/day` | ORDLY → Hub | nie | `{date, label, orders_count, revenue, page, pages, rows[], prev_date, next_date}` — jeden ekran historii |

`priority`: `red` zamówienia, `amber` zwroty / dyskusje / wiadomości, `blue` problem z systemem. Czas `ts` jest w strefie polskiej z przesunięciem (`2026-10-04T12:04:00+02:00`).

## Historia sprzedaży

Ekran „Historia sprzedaży” na Hubie pokazuje jeden dzień naraz (polska doba), od najnowszego zamówienia: godzina, kanał, pierwszy produkt (`+N`, gdy pozycji jest więcej), kwota i login kupującego. Hub nie trzyma historii: o każdy ekran prosi na `ordly/hub/history/get`, a ORDLY odpowiada na `ordly/history/day` (najwyżej 5 wierszy na stronę, `pages` mówi, ile stron ma dzień).

- `orders_count` i `revenue` liczą się tak jak Statystyki i ekran Start: bez zamówień ze statusem `CANCELLED`. Anulowane są na liście z `cancelled: true`.
- `prev_date` / `next_date` to najbliższy starszy / nowszy dzień, w którym coś się sprzedało (puste dni są pomijane). `next_date` = `null` na dziś; po ostatnim dniu ze sprzedażą wskazuje dziś.
- Zła data, data z przyszłości albo zły numer strony = dziś / ostatnia strona.
- Sprzedaże z OLX (sam mail, bez kwoty) nie są zamówieniami w ORDLY, więc ich tu nie ma.

Kod: `app/services/hub_history_service.py`, testy `tests/integration/hub/test_hub_history_service.py`.

## Skąd biorą się zdarzenia

| Zdarzenie ORDLY | Na Hubie | Znika samo, gdy |
|---|---|---|
| `OrderCreated` (Allegro, Allegro Lokalnie) | czerwone `new_order` | zamówienie w pakowaniu, anulowane, z numerem przesyłki albo dalej w realizacji |
| `OlxEventDetected` sprzedaż | czerwone `new_order` (bez kwoty) | tylko OK |
| `OrderReturnCreated`, zwrot z maila | pomarańczowe `return_requested` | zwrot zamknięty |
| `DisputeNoticeDetected` | pomarańczowe `dispute` | tylko OK |
| wiadomość z Allegro Lokalnie / OLX | pomarańczowe `message` | tylko OK |
| alert `SyncFailureTracker` (Allegro, poczta) | niebieskie `system_problem` | kanał znów odpowiada |

Stan leży w tabeli `hub_events` (migracja 0014). Klucz źródła (`order:allegro:<id>` itd.) jest unikalny: zamówienie potwierdzone OK nie wraca na Hub przy kolejnej synchronizacji. Potwierdzony problem z systemem nie wraca, dopóki trwa ta sama seria awarii.

Job co `HUB_PUBLISH_INTERVAL_SECONDS` sprawdza problemy z systemem, zamyka zdarzenia, których sprawa zmieniła się w ORDLY bez osobnego zdarzenia (np. od razu nadana paczka), i wysyła stan oraz statystyki.

## Kod

- `app/infrastructure/mqtt/hub_bridge.py` — połączenie (aiomqtt), ponawianie, LWT
- `app/services/hub_events_service.py` — co i kiedy idzie do Huba
- `app/repositories/sqlite_hub_event_repository.py`, `app/domain/entities/hub_event.py`
- `app/event_subscriptions.py` → `register_hub_subscriptions`
- testy: `tests/integration/hub/` (w tym prawdziwy protokół MQTT na `tests/fakes/mini_mqtt_broker.py`)

Ręczny podgląd na Pi: `mosquitto_sub -h localhost -u ordly -P '<hasło>' -t 'ordly/#' -v`.
