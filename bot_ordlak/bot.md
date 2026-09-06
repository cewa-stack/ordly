# Ordlak — asystent ORDLY

Ordlak to czat wbudowany w ORDLY, który odpowiada na pytania o własny
sklep: ile się sprzedało, co ma niski stan, co czeka na wysyłkę, jakie dni
sprzedażowe się zbliżają. Jedna zakładka w pasku bocznym, jeden ekran.

> **Historia:** do 6 września 2026 Ordlak był generatorem ofert Allegro
> (tytuł, opis HTML i cena z notatki + zdjęć). Generator został **usunięty
> na życzenie użytkownika** — codzienną potrzebą okazało się raportowanie,
> nie wystawianie. Kod generatora i jego pełna specyfikacja siedzą
> w historii Gita; migracja `0007_create_ordlak_generations` zostaje
> w repo (migracji się nie usuwa), a tabela `ordlak_generations` zostaje
> w bazie na Pi razem z zapisanymi ofertami. Jeśli kiedyś ma zniknąć,
> trzeba dopisać osobną migrację — świadomie.

---

## 1. Zasada naczelna: liczby z bazy, nie z modelu

Model **nie zna** żadnych danych sklepu. Dostaje wyłącznie narzędzia,
którymi może o nie zapytać, a system prompt zabrania mu zgadywania
i szacowania. Każdą liczbę z odpowiedzi da się sprawdzić, klikając w ten
sam ekran w aplikacji.

Pod każdą odpowiedzią widać, z których narzędzi Ordlak skorzystał
(`used_tools`). To jedyny sposób, żeby użytkownik odróżnił raport od
gadania — bez tego czat byłby ładnie brzmiącą wróżbą.

## 2. Czego Ordlak NIE robi

Nie wysyła maili, nie zmienia stanów magazynowych, nie wystawia ofert
i nie zmienia niczego w aplikacji. Poproszony o akcję wskazuje ekran, na
którym użytkownik zrobi ją sam.

To świadome ograniczenie, nie brak czasu: dopóki asystent tylko czyta,
jego pomyłka kosztuje jedno zdanie, a nie rozjechany magazyn. Zdejmowanie
tego ograniczenia (np. „wyślij zamówienie do hurtowni") ma być osobną,
świadomą decyzją z własnym potwierdzeniem w UI — nie efektem ubocznym.

## 3. Narzędzia

Wszystkie w `backend/src/app/services/ordlak_assistant_service.py`
(stała `TOOLS` + metody `_tool_*`).

| Narzędzie | Co czyta | Źródło |
|---|---|---|
| `podsumowanie_sprzedazy` | zamówienia, przychód, kanały, topka produktów, przychód dzień po dniu | `OrderRepository` |
| `niskie_stany` | pozycje na progu minimalnym lub poniżej | `InventoryService.get_shopping_list` |
| `magazyn` | stan magazynowy, z opcjonalnym szukaniem po nazwie/SKU | `InventoryService.get_stock_overview` |
| `prognoza_zapasow` | na ile dni starczy zapasu, wartość magazynu, produkty bez sprzedaży | `InventoryService.get_report` |
| `ostatnie_zamowienia` | ostatnie zamówienia albo tylko czekające na wysyłkę | `OrderRepository` |
| `zwroty` | ostatnie zwroty klientów | `ReturnsService` |
| `kalendarz_sprzedazowy` | nadchodzące dni sprzedażowe i święta w Polsce | `domain/sales_calendar.py` |
| `szukaj` | zamówienia po numerze, loginie kupującego albo nazwie produktu | `SearchService` |
| `dyskusje` | lista dyskusji i reklamacji (na żywo z Allegro) | `IssuesService` |
| `watek_dyskusji` | cała rozmowa jednej dyskusji, od najstarszej wiadomości | `IssuesService` |
| `poczta` | maile od marketplace wykryte w skrzynce | `MailboxService` |
| `kalkulator_ceny` | cena sprzedaży przy zadanej marży | `calculate_price` (Python) |
| `stan_systemu` | synchronizacja, połączenie z Allegro, dzisiejsze liczby | `HealthService` + `DashboardService` |

Asystent dostaje **gotowe serwisy, nie repozytoria** — ma widzieć
dokładnie te same liczby co ekrany aplikacji (magazyn liczy podprodukty,
prognoza ma swoje okno), a to jest wiedza serwisów.

Liczby zbiorcze (ile zamówień, za ile) idą z agregatów repozytorium i są
dokładne. Rozbicie na kanały i topka produktów są liczone z próbki
ostatnich 400 zamówień — narzędzie mówi o tym wprost w odpowiedzi, żeby
model nie przedstawił próbki jako statystyki „ze wszech czasów".

Okresy: `dzis`, `wczoraj`, `7dni`, `30dni`, `biezacy_miesiac`. Dni liczone
od północy UTC, tak samo jak `StatsService` i `DashboardService` — inaczej
„dzisiaj" u asystenta znaczyłoby co innego niż „dzisiaj" na ekranie Start.
Repozytorium umie tylko „od daty", więc zamknięty przedział (`wczoraj`)
powstaje przez odjęcie dzisiejszego ogona.

### Odpowiedzi na dyskusje

Asystent czyta wątek (`watek_dyskusji`) i **proponuje** treść odpowiedzi -
nigdy jej nie wysyła. Wysyła użytkownik, na ekranie Dyskusje. Sam tekst
propozycji ma być ostatnim akapitem odpowiedzi, bez cudzysłowów
i komentarza po nim, żeby dało się go skopiować jednym ruchem (przycisk
**Kopiuj** pod każdą odpowiedzią).

### Cena: jedyna liczba spoza bazy

`calculate_price` w `ordlak_assistant_service.py` jest jedynym wyjątkiem od
reguły „asystent tylko czyta bazę": liczba, której nie ma w żadnej tabeli,
ale która musi być powtarzalna i audytowalna. Liczy ją Python, nigdy model
- system prompt zabrania liczenia ceny w pamięci.

Wzór uwzględnia nieoczywistą regułę Allegro: prowizja naliczana jest od
SUMY ceny i kosztu wysyłki pobranego od kupującego, nie od samej ceny.

```
P = (zakup + sprowadzenie + prowizja% * wysyłka_do_kupującego)
    / (1 - prowizja% - marża%)
```

To ten sam wzór, który miał usunięty generator ofert - został, bo jego
wynik był realnie używany. Testy pilnują, że dla tych samych danych daje
te same liczby co przedtem (57,00 zł przy zakupie 25 zł, prowizji 10%,
marży 30%, sprowadzeniu 8 zł i wysyłce 12 zł).

## 4. Kalendarz sprzedażowy ma bliźniaka

`backend/src/app/domain/sales_calendar.py` powtarza dane z
`desktop/src/renderer/src/lib/salesCalendar.ts` — ekran Kalendarz liczy je
lokalnie w rendererze, a asystent odpowiada po stronie Pi i musi znać te
daty bez pytania aplikacji. **Każde dodane lub zmienione wydarzenie trzeba
nanieść w obu plikach**, inaczej Kalendarz i asystent zaczną mówić co
innego o tym samym dniu.

Uwaga na konwencję dnia tygodnia: TypeScript liczy od niedzieli
(`Date.getDay()`), Python od poniedziałku (`date.weekday()`) — Black Friday
to `weekday: 5` w TS i `weekday=4` w Pythonie.

## 5. Kontrakt API

`GET /api/v1/ordlak/status` → `{"configured": true, "model": "claude-sonnet-5"}`

Ekran pyta o to przed pokazaniem pola tekstowego, żeby od razu powiedzieć
„brak klucza na Pi" zamiast pozwolić napisać pytanie i dopiero wtedy
pokazać błąd (ta sama zasada co przy `GET /api/v1/mail/status`).

`POST /api/v1/ordlak/chat`

```jsonc
// żądanie - JEDNO pytanie; historia żyje w bazie na Pi
{ "message": "Ile sprzedałem w tym tygodniu?", "conversation_id": 12 }

// odpowiedź
{ "conversation_id": 12, "reply": "W tym tygodniu…", "used_tools": ["podsumowanie_sprzedazy"] }
```

Pominięty `conversation_id` zakłada nowy wątek; jego tytuł powstaje
z pierwszego pytania (do 60 znaków). Roli `system` nie da się przysłać
z aplikacji — instrukcje asystenta ustala backend.

`GET /api/v1/ordlak/conversations` — lista wątków (bez treści),
od ostatnio używanego.
`GET /api/v1/ordlak/conversations/{id}` — jeden wątek z pełną historią.
`DELETE /api/v1/ordlak/conversations/{id}` — usuwa wątek z wiadomościami.

Kody błędów: `503` gdy brak `ANTHROPIC_API_KEY` na Pi, `404` gdy wskazany
wątek nie istnieje, `422` gdy Anthropic odrzucił zapytanie albo model po
`MAX_TOOL_ROUNDS` (6) rundach dalej tylko pytał o dane.

### Zapisywanie rozmów

Wątki i wiadomości leżą w tabelach `ordlak_conversations`
i `ordlak_messages` (migracja `0010`). `used_tools` zapisujemy razem
z odpowiedzią, a nie liczymy na nowo: wracając do wątku sprzed tygodnia
trzeba widzieć narzędzia, które WTEDY dały tamte liczby.

Pytanie zapisuje się **przed** odpytaniem modelu - gdy Anthropic odmówi
albo padnie sieć, użytkownik wraca do wątku i widzi, o co pytał, zamiast
zastanawiać się, czy pytanie w ogóle wyszło.

Do modelu leci tylko ostatnie `MAX_HISTORY_TURNS` (20) wypowiedzi wątku -
dłuższa historia kosztowałaby przy KAŻDEJ kolejnej odpowiedzi, a raport
i tak dotyczy ostatniego pytania.

## 6. Konfiguracja (`.env`)

```
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-5
```

**To NIE jest subskrypcja Claude Pro/Claude Code** — osobny klucz API
z billingiem per-użycie z `console.anthropic.com`. Bez klucza ekran działa
i mówi o tym wprost, a `POST /ordlak/chat` zwraca 503.

Model domyślny `claude-sonnet-5` to decyzja produktowa, nie przypadek.

## 7. Architektura (rozmieszczenie w repo)

| Warstwa | Pliki |
|---|---|
| Domena | `domain/sales_calendar.py`, `domain/entities/ordlak_conversation.py`, `domain/interfaces/ordlak_conversation_repository.py` |
| Baza | `database/models/ordlak_conversation_model.py`, migracja `0010_create_ordlak_conversations.py` |
| Repozytorium | `repositories/sqlite_ordlak_conversation_repository.py` |
| Serwis | `services/ordlak_assistant_service.py` (pętla narzędzi, klient Anthropic, kalkulator ceny) |
| API | `api/endpoints/ordlak.py`, schematy w `api/schemas.py` |
| Config | `OrdlakSettings` w `core/config.py` |
| Desktop (main) | `desktop/src/main/ipc/ordlak.ts` (czat + zapis odpowiedzi do pliku) |
| Desktop (UI) | `desktop/src/renderer/src/screens/OrdlakScreen.tsx`, `components/OrdlakMascot.tsx`, `SparkIcon` |
| Testy | `tests/unit/services/test_ordlak_assistant_service.py`, `tests/unit/domain/test_sales_calendar.py`, `tests/integration/api/test_ordlak_endpoints.py`, `tests/integration/repositories/test_sqlite_ordlak_conversation_repository.py`, `tests/fakes/fake_anthropic.py`, `tests/fakes/fake_ordlak_conversation_repository.py` |

## 8. Wdrożenie

`git pull` + **`alembic upgrade head`** (migracja `0010` - tabele rozmów)
+ `sudo systemctl restart ordly`. Żadnych nowych zależności, `.env` bez
zmian — asystent chodzi na tym samym `ANTHROPIC_API_KEY`, co dawny
generator.

## 9. Poza zakresem (świadomie odłożone)

- **Asystent w aplikacji mobilnej.** Czat na telefonie to osobny ekran do
  zaprojektowania; backend jest gotowy i nie wymaga zmian.
- **Akcje zapisujące** — patrz sekcja 2.
- **Powiadomienia z własnej inicjatywy** (poranny briefing, alert przed
  brakiem). Świadoma decyzja użytkownika: Ordlak odzywa się wyłącznie
  wtedy, gdy się go zapyta.
