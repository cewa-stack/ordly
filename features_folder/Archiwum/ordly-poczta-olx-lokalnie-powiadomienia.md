# ORDLY — Poczta OLX i Allegro Lokalnie: filtr marketingu + pełna obsługa zdarzeń

## Kontekst i decyzja architektoniczna (ustalona z użytkownikiem)

- **Sprzedaż z maila OLX ma tworzyć pełnoprawne zamówienie ORDLY**
  (odjęcie stanów magazynowych, statystyki, lista „do spakowania")
  — dokładnie na wzór tego, co już działa dla Allegro Lokalnie w
  `services/allegro_lokalnie_orders_service.py`. To NIE jest tylko
  powiadomienie „coś się wydarzyło" — z kompletem danych ma powstać
  `Order`, tak jak przy sprzedaży z Allegro.pl czy Allegro Lokalnie.
- Wiadomość od klienta i zwrot/reklamacja — z obu kanałów (OLX i
  Lokalnie) — zostają **powiadomieniami**, nie zamówieniami (tak jak
  dziś działa `EVENT_NEW_MESSAGE`/`EVENT_INTEREST` dla Lokalnie).

## Problem #1 — maile marketingowe trafiają do skrzynki ORDLY

Zrzuty ekranu pokazują dwa różne nadawcy per serwis:

| Serwis | Nadawca **prawdziwych** powiadomień (zachować) | Nadawca **marketingu** (wykluczyć) |
|---|---|---|
| OLX | `noreply@olx.pl` — „Wiadomości dotyczące ogłoszeń" | `powiadomienia@marketing.olx.pl` — „Wow – 70% rabatu…" |
| Allegro | (istniejący, obsługiwany już przez `allegro_notifications.py`) | `hello@newsletter.allegro.pl` — „Odbierz kupon…" |

### Przyczyna
`core/config.py`, `MailWatchSettings.watch_senders_raw` (domyślnie
`"allegro,olx"`) trafia do `ImapWatcher.fetch_new_from_senders()`, który
robi `IMAP SEARCH FROM "olx"` / `FROM "allegro"` — **dopasowanie
podciągu**. `powiadomienia@marketing.olx.pl` zawiera podciąg `"olx"`,
`hello@newsletter.allegro.pl` zawiera podciąg `"allegro"` — oba
przechodzą filtr i lądują w skrzynce ORDLY tak samo jak prawdziwe
powiadomienia o sprzedaży.

### Rozwiązanie — lista wykluczeń, sprawdzana PO stronie klienta
Dodaj do `MailWatchSettings` nowe pole:
```python
exclude_senders_raw: str = Field(
    default="marketing.olx.pl,newsletter.allegro.pl", alias="MAIL_EXCLUDE_SENDERS"
)

@property
def exclude_senders(self) -> list[str]:
    return [s.strip().lower() for s in self.exclude_senders_raw.split(",") if s.strip()]
```

W `MailboxService.sync_now()`, zaraz po `watcher.fetch_new_from_senders(...)`,
odfiltruj wiadomości, których nadawca zawiera którykolwiek fragment z
`exclude_senders`, **zanim** trafią do `self._mail_repository.save(...)`:

```python
messages = await watcher.fetch_new_from_senders(self._settings.watch_senders, since)
messages = [
    m for m in messages
    if not any(fragment in m.sender.lower() for fragment in self._settings.exclude_senders)
]
```

To musi się stać PRZED zapisem do bazy — marketing nie ma nigdy trafić
do `mail_messages`, żeby nie zaśmiecał skrzynki w aplikacji ani nie
wchodził (przypadkiem, w przyszłości) do klasyfikacji zdarzeń.

**Nie zmieniaj** `classify_sender()` ani `watch_senders` (IMAP SEARCH ma
zostać szerokie/tanie) — filtr wykluczeń to osobny, świadomy krok, łatwy
do rozszerzenia, gdy dojdzie kolejny nadawca marketingowy.

### Kryterium akceptacji
Po wdrożeniu: `POST /api/v1/mail/sync` na skrzynce z zaległym mailem od
`powiadomienia@marketing.olx.pl` NIE dodaje go do `mail_messages` (test
integracyjny z fixture takiego nadawcy). Prawdziwe powiadomienia
(`noreply@olx.pl`, dotychczasowi nadawcy Allegro/Lokalnie) przechodzą
bez zmian.

## Problem #2 — OLX nie generuje żadnych zdarzeń w ORDLY

Cytat z `MailboxService.publish_mail_events`: *"Poczta OLX i pozostała
nie generuje dziś żadnych zdarzeń."* Zero powiadomień o sprzedaży,
wiadomości czy zwrocie z OLX — dokładnie luka, o którą pytasz.

## Etapy wdrożenia

### Etap 0 — zbierz prawdziwe próbki maili OLX (WARUNEK WSTĘPNY)
**Nie zgaduj wzorców tematu/treści.** Moduł `allegro_lokalnie.py` ma
wprost udokumentowaną historię: pierwsza wersja zgadywała szablony i
myliła się w połowie przypadków (dopasowywała np. etykietę interfejsu
"kup teraz" jako nazwę zdarzenia). Zanim napiszesz choć jedną linię
parsera OLX:
1. Poproś o przekazanie/wklejenie treści (najlepiej surowego źródła
   maila, Pokaż źródło/Wyświetl oryginał) **co najmniej jednego
   prawdziwego** przykładu każdego z 3 zdarzeń: sprzedaż, wiadomość od
   kupującego, zwrot/reklamacja z `noreply@olx.pl`.
2. Zapisz je jako fixtures w `backend/tests/fixtures/olx/` (ten sam
   układ co `tests/fixtures/allegro_lokalnie/`).
3. Dopiero na podstawie realnych próbek buduj wzorce w kroku poniżej.
   Nierozpoznany temat ma dawać `EVENT_UNKNOWN`, nigdy zgadywany typ.

### Etap 1 — filtr marketingu (Problem #1)
Wdróż `exclude_senders` jak opisano wyżej. Deployowalne i testowalne
niezależnie od reszty — zrób to jako pierwszy, samodzielny commit.

### Etap 2 — encja i parser zdarzeń OLX
Analogicznie do `domain/entities/allegro_lokalnie_event.py` i
`infrastructure/mail/olx.py` (nowy plik):

```python
# domain/entities/olx_event.py
EVENT_NEW_ORDER = "new_order"
EVENT_NEW_MESSAGE = "new_message"
EVENT_RETURN = "return"          # patrz też Etap 5 - Lokalnie dostaje to samo
EVENT_UNKNOWN = "unknown"

@dataclass(frozen=True, slots=True)
class OlxEvent:
    message_id: str
    event_type: str
    subject: str
    snippet: str
    received_at: datetime
    listing_title: str | None = None
    buyer_login: str | None = None
    quantity: int | None = None
    unit_amount: Decimal | None = None
    amount: Decimal | None = None
    order_id: str | None = None   # odpowiednik transaction_id z Lokalnie

    @property
    def can_become_order(self) -> bool:
        return (
            self.event_type == EVENT_NEW_ORDER
            and self.order_id is not None
            and self.listing_title is not None
            and self.quantity is not None
            and self.amount is not None
        )
```

Pola dopasuj do tego, co REALNIE jest w próbkach z Etapu 0 — powyższe to
punkt wyjścia, nie ostateczny kształt. Jeśli OLX w mailu sprzedażowym
nie podaje osobno ceny jednostkowej, zostaw `unit_amount = amount`
(analogicznie do sytuacji, gdyby brakowało tego pola u Lokalnie).

`infrastructure/mail/olx.py`: parser rozpoznający `EVENT_NEW_ORDER` /
`EVENT_NEW_MESSAGE` / `EVENT_RETURN` **po temacie maila**, z tymi samymi
dwiema zasadami co w `allegro_lokalnie.py` (klasyfikacja po temacie, nie
po treści; nierozpoznane = `unknown`, nie zgadywanie). Numer
zamówienia/oferty wyciągnij z treści (link do ogłoszenia albo numer
transakcji — sprawdź w próbkach, co OLX faktycznie podaje jako stabilny
identyfikator).

### Etap 3 — zdarzenie domenowe i serwis tworzenia zamówień
`core/event_bus/events.py`: dodaj `OlxEventDetected` (kopia
`AllegroLokalnieEventDetected` ze zmienionym typem `event: OlxEvent`).

`services/olx_orders_service.py` (nowy plik, kopia wzorca z
`allegro_lokalnie_orders_service.py`):
```python
MARKETPLACE_OLX = "olx"
STATUS_PAID = "PAID"

class OlxOrdersService:
    async def create_from_event(self, event: OlxEvent) -> Order | None:
        ...  # ta sama logika: can_become_order, dedupe po order_id, save
```
`external_id` zamówienia = identyfikator z maila OLX (Etap 2). Reszta
mapowania (`Product`, `Customer`, `fulfillment_status=FULFILLMENT_NEW`)
1:1 z Lokalnie.

### Etap 4 — wpięcie w `event_subscriptions.py`
Nowy handler `handle_olx_event`, kopia `handle_allegro_lokalnie_event`:
- `can_become_order` + kompletne dane → `container.olx_orders_service(session).create_from_event(...)`
  → sukces → publikuj `OrderCreated` (ten sam tor co Lokalnie: magazyn,
  statystyki, powiadomienie „Nowe zamówienie").
- W przeciwnym razie → `container.notifier().notify_olx_event(detected)`
  (nowa metoda, patrz Etap 6) — wiadomość od klienta, zwrot,
  nierozpoznany szablon.
- Zapisz w audycie (`event_type="OlxEventDetected"`) tak jak dla
  Lokalnie.

Zarejestruj: `container.event_bus.subscribe(OlxEventDetected, handle_olx_event)`.

Nie zapomnij dopisać `container.olx_orders_service()` w `container.py`
(fabryka analogiczna do `allegro_lokalnie_orders_service()`).

### Etap 5 — Allegro Lokalnie: wydziel zwrot jako osobne zdarzenie (parytet)
Dziś `EVENT_ORDER_STATUS` w `allegro_lokalnie.py` łączy w jednym worku
„zwrot" z „paczka dostarczona" i „anulowano" — a w katalogu powiadomień
push (`push_payload.py`, `_ALLEGRO_LOKALNIE_TITLES`) wszystkie dostają
ten sam, ogólny tytuł „Zmiana zamówienia". To dokładnie ta sama luka,
o której mówisz przy OLX: zwrot wymaga Twojej reakcji, dostarczenie
paczki — nie, a oba brzmią dziś tak samo.

Zmiana:
1. W `domain/entities/allegro_lokalnie_event.py` dodaj `EVENT_RETURN = "return"`.
2. W `infrastructure/mail/allegro_lokalnie.py`, `_SUBJECT_RULES`: wydziel
   wzorzec `"zwrot"` z grupy `EVENT_ORDER_STATUS` do własnej grupy
   `EVENT_RETURN` (sprawdź na fixtures z `tests/fixtures/allegro_lokalnie/`,
   czy zwrot ma odrębny, rozpoznawalny temat — jeśli nie, dopisz o tym
   notatkę i zostaw jak jest, nie zgaduj).
3. W `push_payload._ALLEGRO_LOKALNIE_TITLES` i analogicznym miejscu w
   `TelegramNotifier`: `"return": "Zwrot / reklamacja"`.

### Etap 6 — powiadomienia (Telegram + Web Push) dla OLX
`domain/interfaces/notifier.py`: dodaj
`async def notify_olx_event(self, event: OlxEvent) -> None`.

`infrastructure/telegram/telegram_notifier.py`: implementacja z
formatem HTML w stylu istniejących metod (`<b>Tytuł</b>` + treść),
osobne warianty tekstu per `event.event_type` (sprzedaż idzie jako
`OrderCreated`, więc tu realnie trafiają tylko `new_message`, `return`,
`unknown`).

`infrastructure/webpush/web_push_notifier.py` + `push_payload.py`: NOWY
builder `olx_event(...)`, **budowany z katalogu, nie przez
`send_text`** — dokładnie tak jak `allegro_lokalnie_event()` i
`unmatched_products()` już to robią (żeby uniknąć powtórki błędu z
HTML-em wyciekającym na push, opisanego w poprzednim pliku naprawczym).
Dodaj tytuły analogiczne do `_ALLEGRO_LOKALNIE_TITLES`:
```python
_OLX_TITLES = {
    "new_message": "Nowa wiadomość · OLX",
    "return": "Zwrot / reklamacja · OLX",
    "unknown": "OLX",
}
```

`infrastructure/composite_notifier.py`: dopisz fan-out dla
`notify_olx_event`, tak jak dla `notify_allegro_lokalnie`.

### Etap 7 — testy
- Filtr wykluczeń (Etap 1): test na fixture z `powiadomienia@marketing.olx.pl`.
- Parser OLX (Etap 2): po jednym teście na próbkę z Etapu 0, tak jak
  `tests/` ma dla każdej próbki Lokalnie.
- `OlxOrdersService.create_from_event`: kompletne dane → zamówienie
  zapisane, magazyn odjęty (przez `OrderCreated`); niekomplet → `None`,
  zostaje powiadomieniem.
- Podwójna synchronizacja tego samego maila nie tworzy duplikatu
  zamówienia (dedupe po `order_id`, tak jak Lokalnie po `transaction_id`).
- Zwrot na Lokalnie (Etap 5) dostaje osobny tytuł powiadomienia, różny
  od „paczka dostarczona"/„anulowano".

## Kryteria akceptacji (całość)

1. Maile z `marketing.olx.pl` i `newsletter.allegro.pl` nigdy nie
   trafiają do `mail_messages` ani do skrzynki w aplikacji.
2. Sprzedaż z `noreply@olx.pl` z kompletem danych tworzy `Order` w
   ORDLY — magazyn się zmniejsza, zamówienie jest na liście „do
   spakowania", leci standardowe powiadomienie „Nowe zamówienie · Olx".
3. Wiadomość od kupującego i zwrot z OLX dają osobne, rozpoznawalne
   powiadomienia (Telegram + push), różne od siebie i od „Nowe
   zamówienie".
4. To samo dla Allegro Lokalnie: zwrot ma teraz własny tytuł
   powiadomienia, odróżnialny od zwykłej zmiany statusu.
5. Nierozpoznany szablon maila (z OLX albo Lokalnie) NIE znika po cichu
   — zostaje powiadomieniem z neutralnym tytułem plus wpisem
   `WARNING` w audycie, tak jak dziś działa `unknown` dla Lokalnie.

## Czego NIE robić

- Nie zgaduj wzorców tematu maila OLX bez prawdziwych próbek (Etap 0) —
  to jest udokumentowana lekcja z tego samego modułu dla Lokalnie.
- Nie zwężaj `watch_senders`/`classify_sender` do wykluczenia
  marketingu — użyj osobnej listy `exclude_senders`, sprawdzanej po
  pobraniu wiadomości, żeby dało się ją łatwo rozszerzać bez ryzyka
  odcięcia prawdziwych powiadomień.
- Nie buduj treści powiadomień push przez generyczny `send_text()` z
  HTML-em — zawsze przez dedykowany builder w `push_payload.py` (patrz
  Etap 6 i wcześniejsza naprawa `unmatched_products`).
- Nie twórz zamówienia z niekompletnych danych „na tyle ile się da" —
  brakujące pole ma zostawić zdarzenie jako powiadomienie, nigdy nie ma
  wchodzić do magazynu/statystyk z domyślną/zgadywaną wartością.
