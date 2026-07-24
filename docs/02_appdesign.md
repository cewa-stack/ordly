# TOOM Mobile — system projektowy

> Dokument źródłowy dla wyglądu aplikacji. Zatwierdzony kierunek: **"Bento
> v2"** — siatka kafelków różnej wielkości na ekranie Start, reszta ekranów
> jako listy z hairline'ami (nie karty-w-kartach). Każdy nowy komponent UI
> ma się dać opisać tokenami z §1-3 poniżej — jeśli nie da się, najpierw
> dokładamy token tutaj, potem piszemy komponent.

Historia decyzji (dla pamięci, nie do powielania w kodzie):
- Wariant A "Terminal" i B "Soft Neon" odrzucone na rzecz C "Bento".
- Pierwsza wersja Bento odrzucona jako "wygląda jak AI" — poprawki:
  prawdziwe ikony liniowe zamiast kolorowych kwadratów/kółek, dodana dolna
  nawigacja, sparkline+trend zamiast gołej liczby na limonkowym tle,
  limonka używana chirurgicznie (tylko trend, wypełnienie paska, aktywna
  zakładka), karty bez obwódek/poświaty (różnicowanie tylko odcieniem tła +
  hairline).
- Druga runda poprawek: ikona "niski stan" ujednolicona z ikoną "do
  wysłania" — bez tła, sam kontur (żadna z ikon stanu na ekranie Start nie
  ma kolorowego chipa w tle), suwak poziomych filtrów bez natywnego paska
  przewijania, typografia odchudzona (patrz §2 — wagi max. 600, mniejsze
  rozmiary niż w pierwszym szkicu).

## 1. Kolor

Paleta marki jest ustalona w [branding.md](branding.md) i **nie podlega
zmianie** dla apki. Poniżej rozszerzenie o tokeny potrzebne wyłącznie w UI
(stany semantyczne, powierzchnie, hairline) — nie zastępują brandu, tylko
go uzupełniają.

```ts
// theme/colors.ts
export const colors = {
  // marka — z branding.md, bez zmian
  lime:      "#C6FF00",
  ink:       "#111111", // tło aplikacji (dark-mode-only, patrz §5)
  white:     "#F4F4EF", // tekst podstawowy — ciepły offwhite, nie #FFFFFF

  // powierzchnie (różnicowanie kart tylko odcieniem, bez obwódek)
  surface:   "#191919", // karty, wiersze
  surface2:  "#1F1F1F", // elementy zagnieżdżone w kartach (np. avatar-inicjały)
  hairline:  "rgba(255,255,255,0.07)", // separator zamiast border na kartach

  // tekst pomocniczy — ciepły szary (lekki bias w stronę limonki, nie czysta szarość)
  muted:     "#8C8C80",
  mutedDim:  "#5E5E56",

  // semantyka — ODDZIELNA od akcentu marki, nigdy nie zastępowana limonką
  ok:        "#39D97A",
  warn:      "#FFB020",
  crit:      "#FF5C5C",
} as const;
```

**Zasada użycia limonki (najważniejsza reguła wizualna apki):** limonka
pojawia się WYŁĄCZNIE w:
1. trendzie/wartości hero na ekranie Start ("+12%", liczba sprzedaży),
2. wypełnieniu paska stanu magazynowego, gdy stan jest OK,
3. aktywnej zakładce dolnej nawigacji,
4. aktywnym filtrze/chipie wybranym przez użytkownika,
5. głównym przycisku akcji (CTA), maks. jeden na ekran.

Nigdzie indziej — żadnych teł ikon w kolorze limonki z przezroczystością,
żadnych "chipów" z tłem `lime@10%`. Ikony stanu (niski stan, do wysłania,
sync) są zawsze płaskie, w kolorze `muted`/`white`, bez tła — jedyna
różnica między nimi to sam kształt ikony, nie kolor.

## 2. Typografia

System **nie ładuje** własnego fontu (ograniczenie środowiska podglądu w
przeglądarce podczas projektowania) — w apce docelowej używamy fontów
systemowych przez `expo-font`/domyślne, ale **skala i wagi są ustalone i
obowiązują niezależnie od konkretnego fontu**:

| Rola | Rozmiar | Waga | Uwagi |
|---|---|---|---|
| Powitanie (ekran Start, "Dzień dobry, Kuba") | 15.5 | 600 | nie 18/750 jak w pierwszym szkicu — za ciężkie |
| Wartość hero (sprzedaż dnia) | 25 | 600 | `font-variant-numeric: tabular-nums` |
| Nagłówek sekcji ("Ostatnie zamówienia") | 13 | 600 | |
| Wartość stat-card | 16 | 600 | |
| ID zamówienia / nazwa produktu w liście | 12.5 | 600 | |
| Kwota zamówienia | 12.5 | 600 | tabular-nums |
| Tekst pomocniczy (buyer, SKU, etykiety) | 11.5–12 | 500 | kolor `muted` |
| Zakładka nawigacji | 9.5 | 600 | |

**Zasada:** maksymalna waga w całej aplikacji to **600 (semibold)** — nigdy
700/800. To był główny powód, dla którego pierwsza wersja "wyglądała jak
AI wygenerowane": zbyt duże, zbyt grube liczby. Wszystkie liczby (kwoty,
stany magazynowe, statystyki) mają `font-variant-numeric: tabular-nums`,
żeby kolumny cyfr się wyrównywały.

## 3. Layout, kształt, elewacja

- **Promienie:** 2 wartości w całej apce — `11px` (male kontrolki: ikony,
  avatar-inicjały, chip filtra) i `16-20px` (karty, hero). Żadnych
  przypadkowych wartości pośrednich.
- **Karty bez obwódek.** Różnicowanie względem tła wyłącznie kolorem
  (`surface` na `ink`). Zero `box-shadow`/`border` jako ozdoby — jedyny
  cień w całej apce jest na samym telefonie/tabbarze (realistyczna
  głębia UI systemowego), nie na kartach z danymi.
- **Listy zamiast kart-w-kartach.** Zamówienia i pozycje magazynowe w
  obrębie sekcji to wiersze oddzielone `hairline`, nie osobne karty z
  własnym tłem — karty rezerwujemy dla: hero, stat-card, summary-strip.
- **Dolna nawigacja:** pływający pasek (`position: sticky` u dołu ekranu),
  tło `surface` z `opacity ~0.82` + blur (`expo-blur`, `BlurView` na iOS;
  na Androidzie fallback do pełnego `surface` bez blura — API blur na
  Androidzie jest niespójne), promień `20px`, margines `12px` od krawędzi
  ekranu. Aktywna zakładka: ikona i etykieta w kolorze `lime`/`white`,
  reszta w `mutedDim`. Bez tła/pigułki pod aktywną ikoną.

## 4. Ikony

Wszystkie ikony to **linia** (`stroke`, nie `fill`), grubość `stroke-width:
2`, `stroke-linecap/linejoin: round`, rysowane jako komponenty
`react-native-svg` 1:1 z zatwierdzonego mockupu — nie biblioteka ikon
"z automatu" (Feather/Ionicons), żeby styl pozostał spójny z tym, co
zaakceptowane. Zestaw startowy (nazwy plików w `mobile/src/icons/`):

| Ikona | Plik | Użycie |
|---|---|---|
| Dzwonek | `bell.tsx` | powiadomienia (Start, top bar) |
| Ciężarówka | `truck.tsx` | "do wysłania" |
| Bateria/poziom niski | `low-level.tsx` | "niski stan" — **bez tła**, sam kontur, identyczny sposób renderowania jak `truck.tsx` (żadna z dwóch nie ma chipa koloru w tle) |
| Strzałka w górę | `trend-up.tsx` | trend sprzedaży |
| Dom | `home.tsx` | zakładka Start |
| Paragon | `receipt.tsx` | zakładka Zamówienia |
| Skrzynka | `box.tsx` | zakładka Magazyn |
| Słupki | `bars.tsx` | zakładka Statystyki |
| Lupa | `search.tsx` | wyszukiwarka |
| Chevron | `chevron-right.tsx` | linki "wszystkie →", "raport →" |
| Plus | `plus.tsx` | dodaj produkt / akcja twórcza |

## 5. Tryb ciemny jako świadomy wybór marki

Aplikacja **nie przełącza się** na jasny motyw systemowy — `branding.md`
definiuje tło `#111111` jako tożsamość marki (podobnie jak np. aplikacje
konsol/streamingowe z jednym, stałym, ciemnym motywem). To świadoma
decyzja, nie zaniedbanie — nie implementujemy `useColorScheme()` do
przełączania palety. Jedyne miejsce, gdzie system może wpłynąć na wygląd,
to natywne elementy OS (np. pasek statusu, klawiatura) — te zostają
domyślne.

## 6. Komponenty (specyfikacja funkcjonalna)

Poniżej lista komponentów wspólnych do zbudowania w `mobile/src/components/`
wraz z ich stanami — każdy ma obsłużyć **loading / empty / error**, nie
tylko "happy path" (patrz też §7).

- **`HeroSalesCard`** — sprzedaż dnia + sparkline + trend. Stan `loading`:
  skeleton w kolorze `surface2` pulsujący; `error`: komunikat "Nie udało
  się pobrać danych" + przycisk "Spróbuj ponownie"; brak stanu "empty"
  (0 PLN to poprawna wartość, nie błąd).
- **`StatCard`** — ikona + etykieta + wartość (niski stan / do wysłania).
- **`SyncStatusRow`** — kropka stanu (`ok`/`warn`/`crit`) + "Synchronizacja:
  X min temu". Kropka `crit`, gdy ostatni sync > 15 minut temu (2× interwał
  `SYNC_ORDERS_INTERVAL_SECONDS`).
- **`OrderRow`** — awatar-inicjały, ID, kupujący, kwota, status (kropka +
  etykieta, kolor wg mapy: `NOWE→lime`, `PAKOWANIE→warn`, `WYSŁANE→muted`
  z kropką `ok`, `ANULOWANE→crit`).
- **`StockRow`** — nazwa + SKU, ilość `aktualna/min` (tabular-nums), pasek
  stanu (`lime` gdy OK, `crit` gdy `is_low_stock`), opcjonalna etykieta
  "poniżej minimum — dodaj do zamówienia" gdy niski stan.
- **`FilterChipRow`** — pozioma lista bez widocznego paska przewijania
  (`showsHorizontalScrollIndicator={false}` w RN — odpowiednik naprawionego
  suwaka z mockupu).
- **`SearchBar`** — pole tekstowe ze stanem `focused` (obwódka `lime` 1px —
  jedyne miejsce w apce, gdzie limonka pojawia się jako obwódka, bo to
  stan interakcji, nie ozdoba).
- **`SummaryStrip`** — 3 komórki + separator pionowy `hairline`.
- **`BottomTabBar`** — patrz §3.

## 7. Stany, których mockup nie pokazywał (uzupełnienie na potrzeby budowy)

Mockup HTML pokazywał wyłącznie "happy path" z danymi przykładowymi.
Prawdziwa apka musi obsłużyć:

- **Ładowanie pierwsze (cold start):** pełnoekranowy skeleton w układzie
  docelowego ekranu (te same kształty kart, wypełnione `surface2`), nie
  spinner na środku pustego ekranu.
- **Pull-to-refresh:** natywny wskaźnik RN przefarbowany na `lime` na
  tle `ink`.
- **Brak połączenia z API** (RPi offline / Tailscale rozłączony): baner na
  górze ekranu ("Brak połączenia z TOOM") + dane z cache `react-query`
  wyszarzone (opacity 0.6) zamiast zniknięcia całego ekranu.
- **401 (zły/wygasły token):** przekierowanie do ekranu logowania,
  komunikat "Sesja wygasła, zaloguj się ponownie".
- **Pusty magazyn / brak zamówień:** stan pusty z ikoną + jednym zdaniem
  instrukcji (np. "Magazyn jest pusty. Dodaj pierwszy produkt." — ten sam
  ton co dziś w komunikatach bota, patrz `stock.py`), nie goła pusta lista.

## 8. Odniesienie wizualne

Ostateczny, zatwierdzony mockup HTML (dwa ekrany: Start i Magazyn,
wariant "Bento v2" po wszystkich poprawkach) został wygenerowany w trakcie
sesji projektowej i jest punktem odniesienia 1:1 dla wartości w tym pliku —
w razie rozbieżności między kodem a tym dokumentem, ten dokument wygrywa
(mockup HTML był narzędziem do decyzji, nie źródłem prawdy na stałe).
