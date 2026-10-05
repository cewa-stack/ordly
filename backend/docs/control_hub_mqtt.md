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
| `HUB_WHOLESALE_TEST_MODE` | `true` | zamówienia do hurtowni z Huba idą na adres `SMTP_USER` z dopiskiem, do kogo poszłyby; `false` = prawdziwa wysyłka |

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
| `ordly/hub/wholesale/get` | Hub → ORDLY | nie | `{}` lista hurtowni albo `{wholesaler_id}` jej pozycje |
| `ordly/wholesale/catalog` | ORDLY → Hub | nie | `{version, test_mode, wholesalers: [{id, name, template_id, items}], templates: [{id, name, default}]}` |
| `ordly/wholesale/items` | ORDLY → Hub | nie | `{version, wholesaler_id, ok, items: [{name, qty}]}` |
| `ordly/hub/wholesale/preview` | Hub → ORDLY | nie | `{request_id, version, wholesaler_id, template_id, items: [indeksy]}` |
| `ordly/wholesale/preview` | ORDLY → Hub | nie | `{request_id, ok, wholesaler, to, send_to, test_mode, template, subject, inquiry, items, duplicate_minutes}` |
| `ordly/hub/wholesale/send` | Hub → ORDLY | nie | jak preview + `confirm_duplicate` |
| `ordly/wholesale/result` | ORDLY → Hub | nie | `{request_id, status: sent / already_sent / duplicate / error, message}` |

`priority`: `red` zamówienia, `amber` zwroty / dyskusje / wiadomości, `blue` problem z systemem. Czas `ts` jest w strefie polskiej z przesunięciem (`2026-10-04T12:04:00+02:00`).

## Historia sprzedaży

Ekran „Historia sprzedaży” na Hubie pokazuje jeden dzień naraz (polska doba), od najnowszego zamówienia: godzina, kanał, pierwszy produkt (`+N`, gdy pozycji jest więcej), kwota i login kupującego. Hub nie trzyma historii: o każdy ekran prosi na `ordly/hub/history/get`, a ORDLY odpowiada na `ordly/history/day` (najwyżej 5 wierszy na stronę, `pages` mówi, ile stron ma dzień).

- `orders_count` i `revenue` liczą się tak jak Statystyki i ekran Start: bez zamówień ze statusem `CANCELLED`. Anulowane są na liście z `cancelled: true`.
- `prev_date` / `next_date` to najbliższy starszy / nowszy dzień, w którym coś się sprzedało (puste dni są pomijane). `next_date` = `null` na dziś; po ostatnim dniu ze sprzedażą wskazuje dziś.
- Zła data, data z przyszłości albo zły numer strony = dziś / ostatnia strona.
- Sprzedaże z OLX (sam mail, bez kwoty) nie są zamówieniami w ORDLY, więc ich tu nie ma.

Kod: `app/services/hub_history_service.py`, testy `tests/integration/hub/test_hub_history_service.py`.

## Zamówienia do hurtowni

Ekran „Zamów w hurtowni” na Hubie: hurtownia, szablon, pozycje (ilości jak zapisane w hurtowni), podgląd i wysyłka po przytrzymaniu OK. Hurtownie i szablony edytuje się na desktopie; desktop po każdej zmianie i po starcie wysyła ich kopię na `PUT /api/v1/hub/wholesale/catalog` (tabela `hub_wholesale_catalog`, migracja 0017). Mail składa ORDLY według tych samych reguł co desktop (`app/domain/wholesale_email.py` ↔ `desktop/src/renderer/src/lib/wholesalerTemplate.ts`) i wysyła przez SMTP z `.env`.

Zabezpieczenia (mail jest nieodwracalny):
- adres tylko z kopii hurtowni, nigdy z wiadomości Huba; Hub w ogóle nie dostaje adresów,
- `request_id` unikalny (`hub_wholesale_orders`): powtórzona prośba → `already_sent`, bez drugiego maila; nieudaną (`failed`) można ponowić,
- to samo zamówienie do tej samej hurtowni w ciągu 15 minut → `duplicate`, wysyłka dopiero z `confirm_duplicate`,
- `version` katalogu w prośbie: po zmianie hurtowni na desktopie stara prośba jest odrzucana,
- `HUB_WHOLESALE_TEST_MODE=true` (domyślnie): mail idzie do nadawcy SMTP z tematem `[TEST Hub -> <hurtownia>]`.

Wysłane z Huba trafiają do historii na ekranie Hurtownia w desktopie (`GET /api/v1/hub/wholesale/orders`) i do tabeli `events` (`HubWholesaleOrderSent`).

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
