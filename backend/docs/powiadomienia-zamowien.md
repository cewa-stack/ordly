# Zamówienia: etapy, liczniki i powiadomienia

Jedno miejsce, które mówi, **kiedy** zamówienie wymaga działania i **kiedy**
powstaje / znika każde powiadomienie. Kod jest źródłem prawdy — ten plik
opisuje, gdzie ona siedzi.

## Etap zamówienia (skąd ORDLY to wie)

| Źródło | Co daje | Kiedy |
|---|---|---|
| `GET /order/checkout-forms` (50 najnowszych) | `status`, `fulfillment.status`, `fulfillment.shipmentSummary.lineItemsSent` | co 60 s (`sync_orders_job`), ręczne „Odśwież” w aplikacji, `/sync` w bocie |
| `GET /order/checkout-forms/{id}` | to samo dla otwartych zamówień, które wypadły z listy 50 | w tym samym cyklu, max 25 na cykl, z rotacją |
| `GET /order/checkout-forms/{id}/shipments` | numer przesyłki | od razu, gdy `lineItemsSent` = SOME/ALL; dodatkowo `check_waybills_job` co 60 s |

Zasady ochrony danych:

- brak `status` / `fulfillment.status` w odpowiedzi nie nadpisuje zapisanych wartości,
- pusta lista przesyłek nie kasuje znanego numeru,
- błąd Allegro przy pojedynczym zamówieniu nic nie zmienia w bazie; błąd sieci/5xx przerywa dopytywanie do następnego cyklu,
- awaria całej synchronizacji: dane zostają z ostatniej udanej, po 2. nieudanej próbie z rzędu wychodzi jedno powiadomienie „Allegro nie odpowiada”.

## Jedna reguła „wymaga działania”

`app/domain/fulfillment.py`:

- **`requires_packing`** — czeka na spakowanie: nieanulowane (ani `status`, ani etap), **bez numeru przesyłki**, etap `NEW` lub `PROCESSING`. Etap nieznany (NULL) **nie** czeka — synchronizacja dopytuje o niego Allegro.
- **`awaits_shipment`** — czeka na nadanie: jak wyżej plus `READY_FOR_SHIPMENT`.

Kto z niej liczy:

| Miejsce | Reguła |
|---|---|
| Desktop i telefon: „Do spakowania”, odznaki | pole `requires_packing` z `GET /orders` |
| Plakietka push, raport 9:00 | `AttentionService` → `requires_packing` |
| Bot: czat po czyszczeniu 02:00 | `get_active` = `requires_packing` (SQL) |
| Bot: przypomnienie 20:00 | `get_new_status` = `requires_packing` i etap `NEW` („nietknięte”) |
| Kafel „Do wysyłki”, kandydaci `check_waybills_job` | `get_unshipped_since` = `awaits_shipment` (SQL) |

Zgodność SQL ↔ Python ↔ API pilnuje `tests/integration/repositories/test_order_rules_parity.py`.

## Powiadomienia — warunek utworzenia i zniknięcia

| Powiadomienie | Kanał | Powstaje, gdy | Nie powtarza się, bo | Znika / przestaje obowiązywać |
|---|---|---|---|---|
| Nowe zamówienie | Telegram, push | zamówienie zapisane pierwszy raz | unikalność `(marketplace, external_id)` | Telegram: czyszczenie 02:00; push: zostaje w systemie telefonu |
| Zamówienie anulowane | Telegram, push (ciche) | status zmienia się na `CANCELLED` | zapisany status = kolejny cykl nie widzi zmiany | j.w. |
| SMS „pakujemy” (do klienta) | SMS | etap zmienia się na `PROCESSING` (nie przy uzupełnianiu etapu NULL) | historia SMS (`already_sent`) | — |
| Przypomnienie 20:00 | Telegram | ≥1 zamówienie nietknięte (`NEW`, bez numeru, nieanulowane) | raz dziennie | lista liczona od nowa każdego dnia |
| Czat po 02:00 | Telegram | ≥1 zamówienie `requires_packing` | czyszczenie usuwa wszystkie poprzednie wiadomości bota | kolejne czyszczenie |
| Raport 9:00 | push | cokolwiek czeka (paczki, dyskusje, zwroty) | raz dziennie | — |
| Plakietka na ikonie | push | liczona przy każdym push | — | aktualizuje się przy kolejnym push |
| Allegro nie odpowiada | Telegram, push | 2. nieudana synchronizacja z rzędu | raz na serię awarii | seria zeruje się po udanej synchronizacji |

Ograniczenie: wiadomość Telegram i push o nowym zamówieniu nie są kasowane
w chwili nadania paczki — wiadomości bota nie są powiązane z zamówieniami
(rejestr trzyma tylko ID wiadomości). Liczniki, listy i plakietka zmieniają
się od razu po synchronizacji; stare wiadomości czatu znikają o 02:00.
