# Moduł: Allegro Lokalnie — powiadomienia przez IMAP

## 1. Cel i kontekst

Allegro Lokalnie **nie udostępnia publicznego API** (potwierdzone oficjalnie przez Allegro — brak planów na jego stworzenie). Jedyne wiarygodne i niełamiące regulaminu źródło zdarzeń to **powiadomienia e-mail**, które Allegro Lokalnie wysyła na skrzynkę sprzedającego przy każdym zdarzeniu (nowa wiadomość od kupującego, nowe zainteresowanie ogłoszeniem, nowe zamówienie/rezerwacja, zmiana statusu).

Cel modułu: podpiąć się pod ten strumień e-maili przez IMAP (na Raspberry Pi, jako część istniejącego modułu **Unified Mail Inbox**), sparsować je do znormalizowanych zdarzeń domenowych, i rozesłać dalej dokładnie tym samym torem co zdarzenia z Allegro.pl:
- powiadomienie push (desktop + mobile),
- wpis w zakładce **Zamówienia** (i/lub **Wiadomości**, w zależności od typu zdarzenia).

Świadomie **nie** robimy web scrapingu strony Allegro Lokalnie (headless browser, logowanie sesyjne). To łamie ToS, jest kruche przy każdej zmianie HTML i grozi banem konta — sprzeczne z wymogiem "bez bugów, działa dobrze". IMAP jest stabilnym, oficjalnym kanałem (protokół pocztowy), więc jest to jedyne solidne rozwiązanie.

## 2. Architektura — gdzie to siedzi w ORDLY backend

```
Raspberry Pi (ORDLY backend, FastAPI)
│
├── plugins/
│   ├── allegro/            (istniejący — REST API + OAuth2)
│   ├── amazon/              (istniejący/planowany)
│   └── allegro_lokalnie/    (NOWY — IMAP-only plugin)
│       ├── imap_client.py
│       ├── parser.py
│       ├── event_mapper.py
│       └── plugin.py
│
├── core/
│   ├── event_bus.py         (istniejący Event Bus — publikujemy tu nowe eventy)
│   ├── notifications/       (istniejący system powiadomień)
│   └── mail/                (istniejący moduł IMAP unified inbox — reużywamy połączenie)
│
└── scheduler (APScheduler)
    └── job: imap_poll_allegro_lokalnie (co 60–120s)
```

Dzięki architekturze plugin (opisanej w poprzednich ustaleniach dot. ORDLY backend), dodanie tego modułu **nie wymaga zmian w core** — tylko nowy folder pluginu + rejestracja w evencie startowym.

## 3. Konfiguracja skrzynki

Wymagania wstępne:
- Dedykowana skrzynka e-mail (najlepiej ta sama, na którą zarejestrowane jest konto Allegro Lokalnie), z włączonym dostępem IMAP.
- Zalecane: **hasło aplikacji** (app password), jeśli dostawca poczty (Gmail, Outlook) wymaga 2FA — nie używać głównego hasła do konta pocztowego.

Zmienne środowiskowe (`.env` na Pi):

```env
AL_IMAP_HOST=imap.gmail.com
AL_IMAP_PORT=993
AL_IMAP_USER=twoj.email@gmail.com
AL_IMAP_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
AL_IMAP_FOLDER=INBOX
AL_IMAP_POLL_INTERVAL_SEC=90
AL_SENDER_DOMAIN=allegrolokalnie.pl
```

Jeśli masz już moduł **Unified Mail Inbox (IMAP)** zaplanowany — ten plugin powinien **reużyć to samo połączenie IMAP** (jeden IDLE/poll na skrzynkę), a nie otwierać drugiego równoległego połączenia. Rozróżnienie zdarzeń Allegro Lokalnie od zwykłej poczty odbywa się na poziomie nadawcy/domeny, nie osobnego konta.

## 4. Strategia odpytywania: IMAP IDLE > polling

Zamiast pollingu co 60s (marnuje zasoby, opóźnia powiadomienia), użyj **IMAP IDLE**, jeśli serwer pocztowy go wspiera (Gmail, Outlook — tak):

- Połączenie trwałe, serwer push'uje info "masz nowy mail" natychmiast.
- Fallback: jeśli IDLE się rozłączy (timeout ~29 min wg RFC) — automatyczny reconnect + re-IDLE.
- Dodatkowy **safety-net poll co 5 minut** (nawet gdy IDLE działa) — na wypadek cichej desynchronizacji połączenia. To jest kluczowe dla niezawodności: samo IDLE bez fallbacku to częste źródło "zawieszonych" integracji.

```python
# imap_client.py — szkic
import imaplib
import asyncio
from datetime import datetime, timedelta

class AllegroLokalnieImapClient:
    def __init__(self, host, port, user, password, folder="INBOX"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.folder = folder
        self._conn: imaplib.IMAP4_SSL | None = None

    def connect(self):
        self._conn = imaplib.IMAP4_SSL(self.host, self.port)
        self._conn.login(self.user, self.password)
        self._conn.select(self.folder)

    async def idle_loop(self, on_new_mail_callback):
        while True:
            try:
                self.connect()
                await self._idle_and_wait(on_new_mail_callback)
            except (imaplib.IMAP4.abort, OSError) as e:
                # log + backoff + reconnect
                await asyncio.sleep(10)
            finally:
                self._safe_logout()
```

> Uwaga implementacyjna: `imaplib` nie ma natywnego wsparcia IDLE — potrzebna biblioteka `imapclient` (`pip install imapclient`), która ma `idle()`/`idle_check()` gotowe do użycia. To zdecydowanie bezpieczniejszy wybór niż ręczne implementowanie komendy IDLE po surowym socketcie.

## 5. Identyfikacja i klasyfikacja e-maili

### 5.1 Filtr nadawcy (pierwszy, twardy filtr)

Sprawdzaj nagłówek `From`, czy zawiera domenę nadawcy Allegro Lokalnie (`allegrolokalnie.pl` — do zweryfikowania dokładnej domeny na żywym przykładzie maila, może się różnić: `powiadomienia@allegrolokalnie.pl` lub podobne). Wszystko inne pomijamy na tym etapie — nie marnujemy czasu na parsing nieistotnej poczty.

### 5.2 Klasyfikacja po temacie / treści (drugi filtr)

Typy zdarzeń do rozpoznania (na podstawie realnych wzorców powiadomień Allegro Lokalnie — **wymaga weryfikacji na żywych przykładach z Twojej skrzynki**, bo Allegro może zmieniać szablony bez ostrzeżenia):

| Typ zdarzenia | Sygnał w temacie/treści (przykładowy wzorzec) | Mapowanie w ORDLY |
|---|---|---|
| Nowa wiadomość od kupującego | "Nowa wiadomość", "napisał(a) do Ciebie" | → zakładka **Wiadomości** |
| Nowe zainteresowanie / pytanie o ogłoszenie | "zainteresowanie ogłoszeniem", "chce kupić" | → zakładka **Wiadomości** |
| Nowe zamówienie / rezerwacja (Allegro Lokalnie ma "Kup teraz" z płatnością) | "Nowe zamówienie", "opłacone zamówienie" | → zakładka **Zamówienia** |
| Zmiana statusu zamówienia (odebrane, anulowane) | "status zamówienia", "anulowano" | → aktualizacja rekordu w **Zamówieniach** |

**Rekomendacja:** zanim napiszesz finalne regexy, zbierz 5–10 realnych maili z każdej kategorii (np. przekieruj testowo na siebie / poproś kogoś ze sprzedażą na AL o forward), zapisz jako `.eml` w `tests/fixtures/allegro_lokalnie/`. Parser budowany na zgadywaniu szablonu bez próbek realnych maili to główne źródło przyszłych bugów w tym module.

## 6. Parsowanie treści maila

Maile HTML wymagają solidnego parsera odpornego na drobne zmiany szablonu (nie sztywne regexy na cały HTML, tylko wyciąganie konkretnych, stabilnych fragmentów):

```python
# parser.py — szkic
from bs4 import BeautifulSoup
import re

def parse_allegro_lokalnie_email(raw_html: str, subject: str) -> dict:
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    event_type = classify_event(subject, text)

    return {
        "event_type": event_type,       # "new_message" | "new_order" | "order_status_change" | "interest"
        "listing_title": extract_listing_title(soup),
        "buyer_name": extract_buyer_name(soup),
        "amount": extract_amount(text),          # None jeśli nie dotyczy
        "listing_url": extract_link(soup),
        "raw_snippet": text[:500],                # do debugowania / fallback wyświetlania
        "received_at": None,                      # uzupełniane z nagłówka Date maila
    }
```

Każda funkcja `extract_*` powinna zwracać `None` zamiast rzucać wyjątek przy braku dopasowania — **parser nigdy nie może wywalić całego joba przez jeden nietypowy mail**. Nieudany parsing = zapisz zdarzenie jako `event_type="unknown"` z surowym snippetem i pokaż w UI jako "nowe powiadomienie z Allegro Lokalnie — sprawdź ręcznie", zamiast tracić informację całkowicie.

## 7. Deduplikacja i idempotencja

Krytyczne — bez tego użytkownik dostanie to samo powiadomienie push wielokrotnie (np. po restarcie Pi, po reconn−IDLE, po ręcznym re-scanie).

- Klucz unikalności: `Message-ID` z nagłówka maila (globalnie unikalny, generowany przez serwer pocztowy nadawcy).
- Tabela SQLite:

```sql
CREATE TABLE allegro_lokalnie_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE NOT NULL,      -- nagłówek Message-ID, klucz dedup
    event_type TEXT NOT NULL,
    listing_title TEXT,
    buyer_name TEXT,
    amount REAL,
    listing_url TEXT,
    raw_snippet TEXT,
    received_at TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    notified BOOLEAN DEFAULT 0
);
CREATE INDEX idx_al_events_type ON allegro_lokalnie_events(event_type);
```

Przed przetworzeniem: `INSERT OR IGNORE` na `message_id` → jeśli 0 rows affected, mail już przetworzony, pomiń całą resztę pipeline'u (parsing, powiadomienie, event bus).

## 8. Publikacja zdarzenia (Event Bus)

Zgodnie z istniejącą architekturą Event Bus w ORDLY backend — plugin nie wysyła powiadomień bezpośrednio, tylko publikuje znormalizowany event, a subskrybenci (notification service, WebSocket sync, Expo push) reagują niezależnie:

```python
# event_mapper.py
from core.event_bus import event_bus, DomainEvent

async def publish_allegro_lokalnie_event(parsed: dict):
    event = DomainEvent(
        source="allegro_lokalnie",
        type=parsed["event_type"],       # np. "new_order"
        payload=parsed,
        occurred_at=parsed["received_at"],
    )
    await event_bus.publish(event)
```

Dzięki temu **zero zmian** w istniejącym systemie powiadomień desktop (WebSocket → Electron `Notification`) i mobile (Expo Push Service) — Allegro Lokalnie po prostu staje się kolejnym źródłem eventów obok Allegro.pl, tak samo jak zaplanowane źródło Amazon/OLX.

## 9. UI — zakładka Zamówienia i Wiadomości

Ponieważ Allegro Lokalnie nie ma numeru zamówienia/API-owego ID w tym samym formacie co Allegro.pl, rekord w tabeli `orders` (czy jak nazywa się Twoja wspólna tabela zamówień w ORDLY) powinien mieć pole `source: "allegro_lokalnie"` i `external_ref: message_id`, żeby:

- UI mogło pokazać badge/ikonkę odróżniającą źródło (tak jak zapewne już odróżniasz Allegro/Amazon/OLX/eBay),
- kliknięcie w rekord otwierało `listing_url` (link do ogłoszenia na Allegro Lokalnie), bo **nie ma możliwości zarządzania zamówieniem programowo** — użytkownik i tak musi wejść ręcznie na stronę, żeby np. potwierdzić wysyłkę.

Ważne UX zastrzeżenie do zakomunikowania w interfejsie: te rekordy są **tylko do odczytu / informacyjne** (w przeciwieństwie do Allegro.pl, gdzie możesz zarządzać zamówieniem z poziomu ORDLY). Warto dodać w UI etykietę typu "Allegro Lokalnie — zarządzaj na stronie" żeby nie mylić usera co do zakresu funkcjonalności.

## 10. Powiadomienia push

Reużywasz istniejący mechanizm 1:1:

- **Desktop (Electron):** subskrypcja WebSocket na event `allegro_lokalnie.new_order` / `.new_message` → `new Notification(...)`.
- **Mobile (Expo):** ten sam event → POST do Expo Push Service z odpowiednią treścią, np.:
  - `new_order`: "Nowe zamówienie (Allegro Lokalnie) — {listing_title}, {amount} zł"
  - `new_message`: "Nowa wiadomość (Allegro Lokalnie) od {buyer_name}"

Rozróżnij ikonę/kolor od powiadomień Allegro.pl (np. inny akcent koloru albo prefiks "[AL]"), żeby użytkownik od razu wiedział, że to inny rynek i inny poziom kontroli (patrz punkt 9).

## 11. Obsługa błędów i odporność (zgodnie z wymogiem "bez bugów")

| Scenariusz awarii | Zachowanie |
|---|---|
| IMAP login fail (złe hasło/app password wygasło) | Log ERROR + jednorazowe powiadomienie systemowe "Utracono połączenie ze skrzynką AL" (nie spamuj co 90s) + exponential backoff reconnect (10s → 60s → 5min max) |
| Serwer pocztowy nie wspiera IDLE | Fallback automatyczny na zwykły polling co `AL_IMAP_POLL_INTERVAL_SEC` |
| Mail nie pasuje do żadnego znanego wzorca | Zapisz jako `event_type="unknown"`, oznacz do ręcznego review, **nie** crashuj joba |
| Duplikat (już przetworzony `Message-ID`) | Cicho pomiń, brak powiadomienia, brak duplikatu w DB |
| Szablon maila zmienił się (Allegro zaktualizowało wygląd) | Parser nie rzuca wyjątku (patrz pkt 6) — zdarzenie i tak trafia do bazy jako "unknown", nic nie ginie, tylko wymaga aktualizacji regexów |
| Pi restart w trakcie IDLE | Job scheduler odpala plugin od nowa przy starcie aplikacji, dedup po `message_id` chroni przed powtórką starych maili z ostatnich dni |

## 12. Testy

- **Fixtures:** zbiór realnych `.eml` (zanonimizowanych) w `tests/fixtures/allegro_lokalnie/` — po jednym na każdy typ zdarzenia + minimum jeden "nietypowy"/uszkodzony mail do testu ścieżki `unknown`.
- **Testy jednostkowe parsera:** każdy fixture → sprawdź, że `parse_allegro_lokalnie_email()` zwraca poprawny `event_type` i pola.
- **Test dedup:** ten sam `Message-ID` przetworzony dwa razy → tylko jeden rekord w DB, tylko jedno powiadomienie.
- **Test end-to-end (opcjonalnie, na sandboxowej skrzynce):** wyślij testowy mail podobny do realnego, sprawdź czy event trafia przez cały pipeline do WebSocket/Expo push.

## 13. Kroki wdrożenia (kolejność)

1. Zbierz próbki realnych maili z Allegro Lokalnie (wszystkie typy zdarzeń) → zapisz jako `.eml`.
2. Zweryfikuj dokładną domenę/adres nadawcy i dokładne wzorce tematu na podstawie próbek (nie zgaduj).
3. Zainstaluj `imapclient`, `beautifulsoup4` w środowisku Pi (`pip install imapclient beautifulsoup4 --break-system-packages` jeśli bezpośrednio na systemie, albo do virtualenv projektu).
4. Zaimplementuj `imap_client.py` (IDLE + fallback poll + reconnect).
5. Zaimplementuj `parser.py` + `event_mapper.py`, z testami na fixtures z kroku 1.
6. Dodaj tabelę `allegro_lokalnie_events` (migracja SQLite).
7. Zarejestruj plugin w APScheduler / event bus startup (styl identyczny jak istniejące pluginy).
8. Rozszerz UI: badge źródła w Zamówieniach/Wiadomościach + etykieta "tylko do odczytu".
9. Rozszerz payload powiadomień desktop/mobile o rozróżnienie źródła.
10. Test end-to-end na prawdziwej skrzynce przez min. 2–3 dni obserwacji przed uznaniem za stabilne.

## 14. Ograniczenia do zaakceptowania świadomie

- To jest integracja **best-effort**, nie oficjalne API — jeśli Allegro zmieni szablon maila lub domenę nadawcy, parser przestanie rozpoznawać zdarzenia do czasu aktualizacji regexów. To ryzyko nie do wyeliminowania przy braku API, tylko do zminimalizowania (odporny parsing + fallback "unknown" zamiast cichej utraty danych).
- Brak możliwości zarządzania zamówieniem/ogłoszeniem programowo (potwierdzanie wysyłki, edycja) — tylko odczyt i powiadomienia.
- Opóźnienie zależne od czasu dostarczenia maila przez serwer pocztowy nadawcy (zwykle sekundy, ale nie ma gwarancji SLA jak przy webhooku).
