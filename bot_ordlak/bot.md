# Ordlak — asystent AI do wystawiania ofert na Allegro

> Status: **wdrożone w kodzie 2026-08-09** (etapy 1–8 z sekcji 11). Backend,
> API, IPC i ekran desktopowy gotowe; 259 testów backendu przechodzi,
> `npm run typecheck` i `npm run build` desktopu przechodzą. Zostaje wgranie
> na Pi i wpisanie `ANTHROPIC_API_KEY` — patrz sekcja 12.
>
> Decyzje produktowe podjęte 2026-08-09 (sekcja 0). Jeśli coś się zmieni po
> drodze, aktualizuj ten plik.

## 0. Podjęte decyzje (2026-08-09)

| Temat | Decyzja |
|---|---|
| Grafika | Ordlak dostaje **własną, osobną maskotkę** (nowy zestaw plików, nie wariant Ordiego) |
| Historia generacji | **Zapisywana w bazie SQLite**, przetrwa restart apki |
| Miejsce w UI | **Osobny ekran w Sidebarze** ("Ordlak"), pełnoprawna pozycja menu jak Magazyn/Zamówienia |
| Edycja wyniku | Tytuł i opis to **edytowalne pola** po wygenerowaniu — użytkownik poprawia ręcznie przed skopiowaniem |
| Model AI | **Claude Sonnet 5**, z obsługą obrazów (vision) |
| Prowizja Allegro | **Ręczne pole %** — użytkownik sam wpisuje stawkę za każdym razem, bez listy kategorii |
| Limit zdjęć | **Maksymalnie 3 zdjęcia** na jedną generację |
| Stan produktu | **Rozszerzona skala**: Nowy / Bardzo dobry / Dobry / Uszkodzony |
| Prowizja a wysyłka | Potwierdzone (2026-08-09): Allegro liczy prowizję od `cena + koszt wysyłki do kupującego`, nie od samej ceny — wzór w sekcji 5 to uwzględnia, formularz ma osobne pole na koszt wysyłki do kupującego |
| Regulamin tytułów/opisów | Pobrany lokalnie do [`backend/docs/allegro_regulamin/`](backend/docs/allegro_regulamin/) (stan na 2026-08-09) — tytuł: 12–75 znaków / min. 3 słowa; opis: zakaz reklamy, danych kontaktowych, zachęt do kontaktu poza Allegro, wzmianek o wysyłce |

## 1. Pomysł w skrócie

Użytkownik wrzuca do apki desktopowej ORDLY: krótką notatkę o produkcie +
do 3 zdjęć. Ordlak (AI) zwraca gotowy komplet do wklejenia na Allegro:

1. **Tytuł oferty** — SEO, w limicie znaków Allegro.
2. **Opis produktu** — SEO, gotowy HTML do wklejenia.
3. **Sugerowana cena sprzedaży** — wyliczona z kosztu zakupu, transportu,
   ręcznie podanej prowizji Allegro i docelowej marży.

Tytuł i opis są edytowalne na miejscu, użytkownik poprawia i kopiuje
przyciskiem. Bez automatycznego wystawiania na Allegro (poza zakresem —
sekcja 8).

## 2. Nazwa i maskotka

Osobna postać od "Ordiego" (istniejący wskaźnik stanu systemu w
`Mascot.tsx`). Ordi = stan całej apki, Ordlak = twarz konkretnego modułu.

Potrzebne assety (analogicznie do `mascot_idle/happy/orders/thinking.png`):

- `mascot_ordlak_idle.png` — stan spoczynku na ekranie Ordlaka
- `mascot_ordlak_thinking.png` — w trakcie generowania (odpytywanie API)
- `mascot_ordlak_happy.png` — po udanej generacji

Grafiki dostarcza użytkownik (jak dotychczasowe maskotki) — kod tylko
przygotowuje miejsce (`components/OrdlakMascot.tsx` wzorem `Mascot.tsx`,
`OrdlakPose = "idle" | "thinking" | "happy"`).

## 3. Model danych

Nowa tabela w SQLite, wzorem istniejących modeli w
`backend/src/app/database/models/`:

```python
# database/models/ordlak_generation_model.py
class OrdlakGenerationModel(Base):
    __tablename__ = "ordlak_generations"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime]

    # input
    user_note: Mapped[str]                  # notatka użytkownika
    condition: Mapped[str]                  # "new" | "very_good" | "good" | "damaged"
    purchase_cost: Mapped[float]            # PLN - koszt zakupu towaru
    inbound_shipping_cost: Mapped[float]    # PLN - koszt sprowadzenia towaru do siebie (zakup)
    buyer_shipping_cost: Mapped[float]      # PLN - koszt wysyłki DO KUPUJĄCEGO, wpisany przy wystawianiu oferty
    commission_percent: Mapped[float]       # ręcznie wpisana prowizja Allegro, np. 10.0
    target_margin_percent: Mapped[float]    # docelowa marża
    photo_count: Mapped[int]                # ile zdjęć wysłano (same zdjęcia NIE są przechowywane w DB)

    # output (AI)
    generated_title: Mapped[str]
    generated_description_html: Mapped[str]
    ai_condition_notes: Mapped[str | None]  # co AI zauważyło na zdjęciach

    # output (kalkulacja, deterministyczna, nie AI)
    suggested_price: Mapped[float]

    # edycja użytkownika (jeśli poprawił przed skopiowaniem)
    final_title: Mapped[str | None]
    final_description_html: Mapped[str | None]
```

**Zdjęcia nie są zapisywane trwale** — trafiają do promptu AI (base64, w
pamięci) i są odrzucane po odpowiedzi. Historia trzyma tylko tekst i liczby,
żeby nie rozdymać bazy i nie duplikować zdjęć, które i tak są już w
Magazynie/na Allegro. Jeśli w przyszłości okaże się to niewystarczające
(np. chęć podglądu zdjęć przy starej generacji), można dodać zapis na dysk
— nie teraz.

## 4. Kontrakt API

`POST /api/ordlak/generate` — multipart/form-data (pola + do 3 plików):

```
note: string                    # notatka użytkownika, wymagane
condition: "new"|"very_good"|"good"|"damaged"
purchase_cost: float
inbound_shipping_cost: float    # koszt sprowadzenia towaru do siebie
buyer_shipping_cost: float      # koszt wysyłki do kupującego (ustalany przy wystawianiu oferty)
commission_percent: float
target_margin_percent: float
photos: File[] (0..3)           # jpg/png, walidacja rozmiaru (np. max 5 MB/szt.)
```

Odpowiedź:

```json
{
  "id": 42,
  "title": "...",
  "title_below_target": false,
  "description_html": "...",
  "condition_notes": "krótka ocena stanu na podstawie zdjęć, albo null jeśli brak zdjęć",
  "price_breakdown": {
    "purchase_cost": 25.0,
    "inbound_shipping_cost": 8.0,
    "buyer_shipping_cost": 12.0,
    "commission_percent": 10.0,
    "target_margin_percent": 30.0,
    "commission_amount": 6.9,
    "suggested_price": 57.0
  }
}
```

`POST /api/ordlak/{id}/finalize` — zapisuje `final_title` /
`final_description_html` po ręcznej edycji przez użytkownika (do historii;
opcjonalne wywołanie, nie blokuje kopiowania).

`GET /api/ordlak/history` — lista poprzednich generacji (paginacja jak w
innych list endpointach, np. `?limit=&offset=`).

## 5. Kalkulacja ceny (deterministyczna, NIE przez AI)

**Ważne, zweryfikowane w źródłach (sekcja 5.1): Allegro nalicza prowizję od
sumy ceny produktu I kosztu wysyłki pobranego od kupującego** — nie tylko
od samej ceny. To rozróżnia dwa różne koszty transportu w tym module:

- `purchase_cost` + `inbound_shipping_cost` — koszt zdobycia towaru (zakup
  + jego sprowadzenie do siebie). Zwykły koszt własny, wchodzi wprost do
  kalkulacji.
- `buyer_shipping_cost` — koszt wysyłki, który **kupujący zapłaci przy
  zakupie** (ustalany przy wystawianiu oferty). Od sumy `cena +
  buyer_shipping_cost` Allegro liczy prowizję.

Wyprowadzenie: zysk netto (cena minus prowizja od `cena + wysyłka` minus
koszty własne) ma równać się `target_margin_percent` liczonej od ceny
sprzedaży `P`:

```
P - commission% * (P + buyer_shipping_cost) - purchase_cost - inbound_shipping_cost = target_margin% * P
```

Po przekształceniu:

```
suggested_price = (purchase_cost + inbound_shipping_cost + commission_percent/100 * buyer_shipping_cost)
                   / (1 - commission_percent/100 - target_margin_percent/100)

commission_amount = commission_percent/100 * (suggested_price + buyer_shipping_cost)
```

Przykład: zakup 25 zł, sprowadzenie do siebie 8 zł, wysyłka do kupującego
12 zł, prowizja 10%, marża docelowa 30% → `suggested_price = 57.0 zł`,
`commission_amount = 6.9 zł`.

Walidacja: `commission_percent + target_margin_percent` musi być < 100,
inaczej mianownik wychodzi ≤ 0 — endpoint zwraca 422 z czytelnym
komunikatem po polsku.

Przeliczenie na żywo w UI (suwak marży) odbywa się **po stronie renderera**
w JS — bez nowego zapytania do backendu/AI, bo to czysta matematyka.

### 5.1 Źródło zasady o prowizji

Potwierdzone w materiałach o cenniku Allegro 2026 (kalkulatory prowizji,
poradniki sprzedażowe): prowizja od sprzedaży jest naliczana od łącznej
kwoty transakcji — cena produktu plus opłata za dostawę pobrana od
kupującego. Przykładowo: sprzedaż za 100 zł z dostawą 15 zł → prowizja
liczona od 115 zł, nie od 100 zł. Stawka prowizji zależy od kategorii
(zwykle 5–17%), stąd decyzja z sekcji 0: **wpisywana ręcznie przez
użytkownika** przy każdej generacji, bez domyślnej wartości.

## 6. Prompt / kontrakt z modelem AI

Backend (`ordlak_service.py`) buduje jeden prompt do Claude Sonnet 5 (Anthropic
Messages API, `tool_use` żeby wymusić strukturę JSON zamiast parsować wolny
tekst):

**Wejście do modelu:**
- notatka użytkownika (tekst),
- stan produktu (jedna z 4 wartości, przetłumaczona na opis po polsku dla
  modelu),
- do 3 zdjęć jako `image` content blocks (base64),
- twarde ograniczenia opisane w 6.1/6.2 poniżej (zweryfikowane w
  oficjalnych materiałach Allegro, zapisane też lokalnie w
  [`backend/docs/allegro_regulamin/`](../backend/docs/allegro_regulamin/)).

### 6.1 Zasady tytułu (wymuszone w promptcie i walidacji)

Źródło: [`tytul-oferty.md`](../backend/docs/allegro_regulamin/tytul-oferty.md)
(pobrane z oficjalnej pomocy Allegro + developer portalu, stan na
2026-08-09).

- **Twardy limit regulaminowy: 12–75 znaków, minimum 3 słowa.** (Limit
  dolny obowiązuje od 7 maja 2025 — starsze poradniki mówiące tylko o
  limicie 75 są nieaktualne w tym punkcie.)
- **Cel produktowy Ordlaka: zawsze mierzyć w górną granicę, 74–75
  znaków**, żeby wykorzystać maksimum miejsca na słowa kluczowe pod SEO
  Allegro (algorytm indeksuje dokładnie to, co jest w tytule — im więcej
  trafnych, realnych cech produktu w tytule, tym więcej fraz, na które
  oferta może się wyświetlić). To nie oznacza upychania keywordów —
  oznacza dopisywanie **kolejnych prawdziwych atrybutów produktu**
  (marka, model, kolor, rozmiar, materiał, pojemność, przeznaczenie), aż
  tytuł wypełni dostępne miejsce.
- Tylko cechy dotyczące wystawianego produktu, najważniejsze słowa
  kluczowe na początku, kolejne atrybuty dalej — aż do ~75 znaków.
- Zakaz: powtórzeń słów kluczowych (**wypełnianie długości przez
  powtarzanie tego samego słowa jest zakazane** — trzeba dodawać nowe,
  różne, prawdziwe atrybuty), fraz o obniżkach ("tanio", "najtaniej"),
  słów "okazja"/"nowość"/"promocja"/"hit", informacji o wysyłce/odbiorze
  osobistym/fakturach/loginie/mieście, numerów magazynowych, znaków
  specjalnych jako ozdobników (`@ ! [ ]`), nazw marek niezwiązanych z
  produktem, CAPS LOCKA.
- **Walidacja backendu (`ordlak_service.py`):**
  - poza twardym zakresem 12–75 znaków → odrzucone, błąd zamiast
    wysyłania dalej (regulaminowe minimum);
  - **poniżej 65 znaków** (czyli wyraźnie poniżej celu 74–75, choć wciąż
    "legalne") → backend automatycznie ponawia zapytanie do modelu **raz**
    z dopiskiem w promptcie "tytuł za krótki, dodaj więcej prawdziwych
    atrybutów produktu, docelowo 74–75 znaków"; jeśli druga próba wciąż
    jest poniżej 65, zwracany jest ten wynik (lepszy krótszy trafny tytuł
    niż wymuszony bełkot) wraz z flagą `title_below_target: true` w
    odpowiedzi, żeby UI mogło to zasygnalizować użytkownikowi zamiast
    cichego niedociągnięcia.

### 6.2 Zasady opisu (wymuszone w promptcie)

Źródło: [`opis-oferty.md`](../backend/docs/allegro_regulamin/opis-oferty.md)
(pobrane z oficjalnej pomocy Allegro + regulaminu, stan na 2026-08-09).

Opis ma się skupiać **wyłącznie na cechach i stanie produktu**. Zakaz:
- danych kontaktowych (telefon, e-mail, numer konta),
- zachęt do kontaktu/zakupu poza Allegro (np. "napisz prywatnie", "kontakt
  na priv"),
- fraz reklamowych/marketingowych ("gratis", "tanio", "promocja", "hit",
  "prezent"),
- **wzmianek o wysyłce, dostawie, czasie realizacji, kosztach transportu,
  odbiorze osobistym** — to należy do dedykowanych pól oferty (czas
  wysyłki, cennik dostawy w formularzu Allegro), nie do opisu produktu,
- linków,
- informacji o innych ofertach sprzedawcy, gwarancji, warunkach
  niezwiązanych z samym przedmiotem.

**Narzędzie (tool) definiujące wymagany output:**

```json
{
  "name": "submit_offer_draft",
  "input_schema": {
    "type": "object",
    "required": ["title", "description_html", "condition_notes"],
    "properties": {
      "title": {
        "type": "string",
        "minLength": 12,
        "maxLength": 75,
        "description": "Cel: 74-75 znakow (maksymalne wykorzystanie miejsca pod SEO), zawsze prawdziwe atrybuty produktu, nigdy powtorzenia slow"
      },
      "description_html": {"type": "string"},
      "condition_notes": {"type": "string"}
    }
  }
}
```

Cena **nigdy** nie wychodzi z modelu — nawet jeśli model coś zasugeruje w
tekście, backend to ignoruje i liczy sam (sekcja 5). To świadoma decyzja:
kalkulacja ma być przewidywalna i audytowalna, nie "zgadywana" przez LLM.

**Regeneracja bez uwag**: przycisk "Generuj ponownie" po prostu wywołuje
endpoint jeszcze raz z tymi samymi danymi wejściowymi (model i tak da inny
wariant przy ponownym zapytaniu). Nie ma osobnego trybu "popraw z uwagami"
w V1 — user edytuje wynik ręcznie w polach (patrz sekcja 0).

## 7. UI — ekran "Ordlak" (Sidebar)

Wzorem istniejących ekranów (`ZamowieniaScreen.tsx`, `MagazynScreen.tsx`):

**Panel wejściowy (lewa/górna część):**
- Textarea: notatka o produkcie.
- Dropzone/upload: do 3 zdjęć, miniatury z możliwością usunięcia,
  licznik "2/3".
- Select: stan produktu (Nowy / Bardzo dobry / Dobry / Uszkodzony).
- Input: koszt zakupu (PLN).
- Input: koszt sprowadzenia towaru do siebie (PLN), domyślnie 0.
- Input: koszt wysyłki do kupującego (PLN) — ta wartość, którą sprzedający
  ustawi w formularzu Allegro; potrzebna, bo **od niej też liczy się
  prowizja** (sekcja 5). Domyślnie 0 (np. "darmowa dostawa wliczona w
  cenę").
- Input: prowizja Allegro (%), bez domyślnej wartości — użytkownik wpisuje
  świadomie za każdym razem (żeby nie wystawić po błędnej stawce).
- Suwak/input: docelowa marża (%), domyślnie np. 30%.
- Przycisk "Generuj ofertę" (disabled dopóki notatka + koszt zakupu nie są
  wypełnione; zdjęcia opcjonalne, ale UI zachęca "dodaj zdjęcie dla
  lepszego opisu").

**Panel wyniku (prawa/dolna część), po wygenerowaniu:**
- OrdlakMascot w pozie "thinking" podczas requestu → "happy" po sukcesie.
- Pole tytułu: **edytowalne**, licznik znaków (X/75) kolorowany wg strefy:
  czerwony <12 lub >75 (regulaminowy błąd), żółty 12–64 (poniżej celu
  SEO), zielony 65–75 (cel osiągnięty); jeśli `title_below_target: true`,
  dyskretna podpowiedź "dodaj więcej atrybutów produktu, żeby wykorzystać
  limit znaków". Przycisk "Kopiuj".
- Pole opisu: **edytowalne** (textarea z podglądem HTML obok albo pod
  spodem), przycisk "Kopiuj".
- Notatka AI o stanie produktu (`condition_notes`) — tylko do odczytu, info
  pomocnicze.
- Karta ceny: rozbicie koszt zakupu + sprowadzenie + wysyłka do kupującego
  + prowizja (liczona od ceny + wysyłki!) + marża → cena sugerowana, z
  suwakiem marży przeliczającym na żywo.
- Przycisk "Generuj ponownie".

**Historia** (dół ekranu lub osobna zakładka): lista poprzednich generacji
(tytuł, data, cena), klik = podgląd read-only starego wyniku.

## 8. Konfiguracja (`.env`)

Wzorem istniejących sekcji w `backend/.env.example`:

```
# ============================================
# ORDLAK - generator ofert AI (Anthropic API)
# ============================================
# WAŻNE: to NIE jest subskrypcja Claude Pro/Claude Code - osobny klucz
# API z billingiem per-użycie, wygenerowany na console.anthropic.com.
# Bez tego klucza ekran Ordlak zwróci czytelny błąd zamiast próby wywołania AI.
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-5
# Maks. rozmiar pojedynczego zdjęcia wysyłanego do AI (większe są odrzucane
# z czytelnym błędem zamiast próby wysyłki).
ORDLAK_MAX_PHOTO_SIZE_MB=5
```

## 9. Architektura (rozmieszczenie w repo)

```
backend/src/app/
  services/ordlak_service.py               # prompt, wywołanie Anthropic API, kalkulacja ceny
  api/endpoints/ordlak.py                  # POST /generate, POST /{id}/finalize, GET /history
  api/schemas.py                           # + OrdlakGenerateRequest/Response, OrdlakHistoryItem
  database/models/ordlak_generation_model.py
  repositories/sqlite_ordlak_repository.py
  domain/entities/ordlak_generation.py
  core/config.py                           # + anthropic_api_key, anthropic_model, ordlak_max_photo_size_mb
  container.py                             # spina OrdlakService z repo + config

desktop/src/
  main/ipc/ordlak.ts                       # IPC: generate, finalize, history
  main/lib/apiClient.ts                    # + metody ordlak.*
  preload/index.ts                         # + bridge.ordlak
  types/ordly-bridge.d.ts                  # + typy Ordlak
  renderer/src/screens/OrdlakScreen.tsx
  renderer/src/components/OrdlakMascot.tsx
  renderer/src/components/Sidebar.tsx      # + nowa pozycja menu "Ordlak"
  renderer/src/assets/mascot_ordlak_idle.png
  renderer/src/assets/mascot_ordlak_thinking.png
  renderer/src/assets/mascot_ordlak_happy.png

backend/docs/allegro_regulamin/
  tytul-oferty.md                          # zasady tytułu (limit 12-75 znaków, blacklista fraz) - już pobrane
  opis-oferty.md                           # zasady opisu (zakaz reklamy/kontaktu/wzmianek o wysyłce) - już pobrane
```

Migracja Alembic dla nowej tabeli `ordlak_generations` — wzorem istniejących
w `backend/alembic/versions/`.

## 10. Poza zakresem V1 (świadomie odłożone)

- Automatyczne wystawianie oferty na Allegro przez API (osobny, duży
  projekt — parametry kategorii, warianty, stany magazynowe).
- Automatyczne pobieranie stawek prowizji Allegro per kategoria (V1: ręczne
  pole %).
- Rozpoznawanie kategorii Allegro ze zdjęcia/opisu.
- Tryb "popraw z uwagami" (regeneracja z instrukcją tekstową) — V1 ma tylko
  ręczną edycję pól i zwykłą regenerację.
- Zapis zdjęć w historii (tylko metadane liczbowe/tekstowe — sekcja 3).
- Wielojęzyczne oferty (tylko PL).

## 11. Kolejność budowy (proponowana)

1. Backend: model + migracja + repo + serwis kalkulacji ceny (bez AI,
   testowalne od razu) + testy jednostkowe wzoru z sekcji 5.
2. Backend: integracja Anthropic API (klucz z configu, prompt, tool_use,
   walidacja limitu 3 zdjęć / rozmiaru).
3. Backend: endpointy REST + rejestracja w routerze.
4. Desktop: IPC + apiClient + typy bridge.
5. Desktop: `OrdlakScreen.tsx` — najpierw formularz + wywołanie + wynik
   statyczny (bez edycji/historii), żeby zobaczyć end-to-end.
6. Desktop: edytowalne pola + kopiowanie do schowka.
7. Desktop: panel historii.
8. Grafiki maskotki Ordlaka (dostarcza użytkownik) + `OrdlakMascot.tsx`.

Wszystkie 8 etapów wykonane 2026-08-09.

## 12. Stan wdrożenia (2026-08-09)

### Co powstało

| Warstwa | Pliki |
|---|---|
| Domena | `domain/entities/ordlak_generation.py`, `domain/interfaces/ordlak_repository.py` |
| Baza | `database/models/ordlak_generation_model.py`, migracja `alembic/versions/0007_create_ordlak_generations.py` |
| Repozytorium | `repositories/sqlite_ordlak_repository.py` |
| Serwis | `services/ordlak_service.py` (kalkulacja + Anthropic API) |
| API | `api/endpoints/ordlak.py`, schematy w `api/schemas.py`, rejestracja w `api/router.py` |
| Config | `OrdlakSettings` w `core/config.py`, sekcja w `.env.example` |
| Desktop (main) | `main/ipc/ordlak.ts`, `apiUpload()` w `main/lib/apiClient.ts` |
| Desktop (UI) | `renderer/src/screens/OrdlakScreen.tsx`, `components/OrdlakMascot.tsx`, `lib/ordlakPrice.ts`, `lib/sanitizeHtml.ts`, `SparkIcon` |

Endpointy (wszystkie za `require_api_token`):
`GET /api/v1/ordlak/status`, `POST /api/v1/ordlak/generate` (multipart),
`GET /api/v1/ordlak/history`, `POST /api/v1/ordlak/{id}/finalize`.

### Odstępstwa od specyfikacji (świadome)

- **Dodano `GET /api/v1/ordlak/status`** (nie było w sekcji 4). Powód ten sam,
  co przy skrzynce: bez tego ekran nie umiałby odróżnić „brak klucza na Pi"
  od „coś się zepsuło", a użytkownik dowiadywałby się o braku konfiguracji
  dopiero po wypełnieniu całego formularza.
- **Prefiks `/api/v1/`** zamiast gołego `/api/ordlak/` z sekcji 4 — cała
  reszta ORDLY API żyje pod `/api/v1`, a token (`require_api_token`) jest
  podpięty do tego routera.
- **Bez `strict: true` na narzędziu** `submit_offer_draft`. Structured
  outputs nie wspiera `minLength`/`maxLength`, a te są w schemacie z sekcji
  6.2 — limity pilnuje walidacja w `ordlak_service.validate_title()`, tak jak
  wymaga sekcja 6.1.
- **Nowe zależności backendu:** `anthropic` (SDK) i `python-multipart`
  (FastAPI wymaga jej do `Form`/`UploadFile`). Wymagają `uv sync` na Pi.

### Wdrożenie na Pi

Konieczne kroki poza `git pull`: `uv sync` (nowe zależności),
`alembic upgrade head` (tabela `ordlak_generations`) i wpisanie
`ANTHROPIC_API_KEY` w `~/ordly/backend/.env`. Bez klucza ekran Ordlaka
działa i pokazuje czytelny komunikat, ale generowanie zwraca 503.
