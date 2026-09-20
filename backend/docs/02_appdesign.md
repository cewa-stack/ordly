# ORDLY — system projektowy "Nokturn"

> Dokument źródłowy dla wyglądu obu aplikacji (desktop Electron + mobile
> Expo). Zatwierdzony kierunek: **"Nokturn"** — głęboka zieleń-petrol
> z jednym źródłem światła, teal jako sygnał „teraz", koral jako „czeka
> na Ciebie", maskotka Ordlak jako wskaźnik stanu.
>
> Wartości liczbowe żyją w kodzie
> (`desktop/src/renderer/src/theme/global.css`,
> `desktop/tailwind.config.ts`, `mobile/src/theme/colors.ts`,
> `mobile/src/theme/typography.ts`). Ten plik opisuje **reguły**; przy
> rozbieżności co do konkretnej liczby wygrywa kod, przy rozbieżności co
> do zasady — ten plik.

**Historia:** wariant „Bento v2" (limonka `#C6FF00` na `#111111`,
mobile dark-only) został zastąpiony w całości. Limonka nie występuje już
nigdzie w produkcie. Wcześniejszy rebranding na teal był krokiem
pośrednim; Nokturn go domyka.

## 1. Trzy zasady

Z nich wynika cała reszta. Przy każdej wątpliwości wracaj do nich.

1. **Światło ma kierunek.** Tło to głęboka zieleń-petrol z jedną poświatą
   u góry po lewej. Panele mają górę i dół bez obwódek. Żadnych
   gradientowych zmywów na całą kartę, żadnego szkła.
2. **Blask to komunikat.** Teal świeci tylko tam, gdzie coś dzieje się
   teraz. Koral — gdy coś czeka na użytkownika. Na jednym ekranie świecą
   najwyżej **dwa** punkty.
3. **Ordlak żyje, a nie pozuje.** Każdy jego stan jest pochodną zdarzenia
   w systemie. Nie ma stanów losowych ani dekoracyjnych.

## 2. Kolor

Paleta w [branding.md](branding.md). Tu tylko reguły użycia.

- **Żadnych wartości szesnastkowych w komponentach.** Na desktopie
  jedyne miejsca z kolorami to `theme/global.css` i `tailwind.config.ts`;
  na mobile — `theme/colors.ts`. Kontrolę robi:

  ```bash
  cd desktop/src/renderer/src
  grep -rnE "(bg|text|border|from|to|via|shadow|ring)-\[(#|rgba?\()" --include=*.tsx .
  grep -rnE "#[0-9a-fA-F]{3,8}\b" --include=*.tsx .
  ```

  Obie komendy mają zwracać **zero** trafień.

- **Dwie atmosfery, identyczne klucze.** Mobile ma noc i dzień; klucze
  palety są w obu zestawach takie same (`bg`, `card`, `tx`, `acc`, …),
  więc **żaden komponent nigdy nie pyta, która atmosfera jest aktywna**.
  Jeśli musi zapytać — klucz jest źle zaprojektowany.

- **Przełączanie atmosfery:** godzina (dzień 6:00–20:00) plus ręczne
  nadpisanie w Ustawieniach. Czujnik jasności jest kuszący, ale skacze
  przy każdym przejściu pod lampą.

- **Kolory kanałów sprzedaży są stałe** w obu atmosferach — użytkownik
  uczy się ich jako etykiet. W atmosferze dziennej kanały mają własne,
  kryjące tła, bo przezroczystości z nocy giną na bieli.

- **Kontrast:** `--text-3` (`#6F8882`) daje 4,57:1 na `--panel`,
  `day.tx3` (`#64746E`) daje 4,6:1 na bieli. Obie wartości są dobrane pod
  tekst 9–11 px i stoją na granicy — po zmianie `--panel` albo `day.card`
  przelicz je ponownie.

## 3. Typografia

| Rola | Krój | Rozmiar / waga | Tracking |
|---|---|---|---|
| Powitanie na karcie głównej | Bricolage 700 | 27 px | −0,03em |
| Tytuł ekranu (desktop topbar) | Bricolage 700 | 17 px | −0,02em |
| Tytuł ekranu (mobile) | Bricolage 700 | 24 px | −0,025em |
| Liczba na kaflu KPI | Bricolage 700 | 25–26 px | −0,03em |
| Nagłówek panelu | Bricolage 700 | 14 px | −0,01em |
| Wiersz listy, nazwisko | Instrument Sans 600 | 12,5–13,5 px | 0 |
| Treść, opisy | Instrument Sans 400 | 13 px | 0 |
| Cyfry, numery, godziny | JetBrains Mono 500 | 11–12,5 px | 0,03em |
| Etykieta wersalikami | JetBrains Mono 500 | 9–10,5 px | 0,15em |

**Zasada:** Bricolage wyłącznie w rolach wyróżnionych. Nigdy w wierszu
listy — tam zawsze Instrument Sans albo mono.

Wszędzie, gdzie liczby stoją jedna pod drugą, obowiązuje
`font-variant-numeric: tabular-nums` (RN: `fontVariant: ["tabular-nums"]`).
Bez tego kolumny rozjeżdżają się przy każdej zmianie danych.

W React Native **wagę niesie nazwa rodziny**
(`InstrumentSans_600SemiBold`), nie `fontWeight`. Podanie `fontWeight`
obok własnego kroju jest ignorowane na iOS, a na Androidzie potrafi
podmienić krój na systemowy.

## 4. Kształt i elewacja

- Promienie z tokenów: `7 / 10 / 14 / 20 / 28 / 999`. Żadnych wartości
  pośrednich „na oko".
- **Wybrany element nie ma obwódki** — ma tło `--panel-2` plus pasek
  `--teal` 2 px przy lewej krawędzi. Ten sam wzorzec w nawigacji
  i na wybranym wierszu listy, żeby „wybrane" wyglądało wszędzie tak samo.
- **Jeden cień w całej aplikacji** to `glow-teal` pod przyciskiem
  `primary`. Karty z danymi nie mają cieni ani obwódek jako ozdoby.
- **Ucięta lista ma wygaszenie**, nie ostrą krawędź (30 px od dołu;
  na ekranie asystenta odwrotnie — 34 px od góry).

## 5. Ordlak — maskotka jako wskaźnik

Jeden komponent SVG, sześć stanów, sterowanie atrybutem `data-state`
(desktop) albo propsem `state` (mobile). **Żadnych `id` w SVG** —
komponent montuje się wielokrotnie na jednym ekranie, a duplikaty `id`
psują gradienty i maski.

| Stan | Wyzwalacz |
|---|---|
| `sync` | trwa cykl synchronizacji albo ręczne odświeżenie |
| `happy` | 1,2 s po nowym zamówieniu lub oznaczeniu paczki jako wysłanej |
| `alert` | druga nieudana synchronizacja poczty **pod rząd**, brak łączności z Pi, Allegro nie odpowiada |
| `think` | Ordlak generuje odpowiedź w rozmowie |
| `sleep` | po 22:00 bez zdarzeń; oraz na pustych stanach list |
| `idle` | wszystko pozostałe |

Rozmiary: 22 px (wskaźnik, ikona paska), 26 px (nagłówek), 28 px (awatar
w rozmowie), 40 px (gałka mobilna), 62 px (karta mobilna), 134 px (karta
powitalna desktopu). **Poniżej 22 px Ordlak traci oczy — to dolna
granica.** Nigdy dwa razy na jednym ekranie w rozmiarze większym niż 40 px.

Geometria: viewBox `0 0 128 128`, cała zawartość w grupie przesuniętej
o `-8.4 / -0.5`. Te dwie liczby to wynik pomiaru `getBBox()` na ramce
figury (92,81 × 97, środek w 72,41 / 64,5) — nie zmieniaj ich bez
ponownego pomiaru. Fale muszą być **poza** `.ord-figure`, jako jej
rodzeństwo: wewnątrz psują ramkę figury i punkt obrotu animacji.

## 6. Język statusów

Spójny w całej aplikacji, trzy tony:

| Znaczenie | Ton | Tło / tekst |
|---|---|---|
| Wymaga działania | `hot` | koral 14% / koral |
| W toku, dziś | `go` | teal 16% / teal |
| Zamknięte | `mute` | `--panel-3` / `--text-3` |

„Wysłane", „Odebrane" i „Anulowane" są `mute`, **nie** `go`. Świecenie
rzeczy już skończonych to główny powód, przez który interfejsy robią się
hałaśliwe.

## 7. Listy

- Nagłówek i wiersze mają **identyczną** definicję kolumn (jedna stała
  w module). Każde dziecko potrzebuje `min-width: 0`, inaczej ścieżka
  `1fr` nie skurczy się poniżej swojej zawartości i kwoty wyjdą poza panel.
- **Etykieta kanału ma stałą szerokość** (68 px desktop / 60 px mobile).
  Bez niej „Lokalnie" jest szersze od „OLX" i nazwiska zaczynają się
  w różnych miejscach — to był najbardziej widoczny błąd pierwszej wersji.
- Nazwisko i podwiersz są ucinane wielokropkiem, żeby **każdy wiersz miał
  tę samą wysokość** niezależnie od liczby pozycji.
- Bez pasów zebry. Bez siatki pionowej.
- **Liczba w liczniku panelu musi zgadzać się z liczbą widocznych wierszy.**

## 8. Ruch i dostępność

Jedna krzywa w całej aplikacji: `cubic-bezier(.22,.61,.36,1)`.

| Zdarzenie | Czas |
|---|---|
| Hover, zmiana stanu kontrolki | 150 ms |
| Wejście panelu, przejście ekranu | 280 ms |
| Oddech maskotki | 3,6 s |
| Cykl fal synchronizacji | 1,5 s (przesunięcia 0 / 0,18 / 0,36 s) |

- `prefers-reduced-motion` (RN: `AccessibilityInfo.isReduceMotionEnabled`)
  zatrzymuje **ruch**; stany nadal zmieniają kolor i mimikę.
- Każdy element dotykowy na mobile ma co najmniej 44 × 44 px pola
  trafienia, także zakładki.
- Każdy SVG maskotki ma `role="img"` / `accessibilityRole="image"`
  i etykietę „Ordlak". **Stan nie jest w etykiecie** — czytnik ekranu nie
  ma powtarzać „Ordlak synchronizuje" przy każdym odświeżeniu. Stan
  komunikuje tekst obok.

## 9. Stany, które trzeba obsłużyć

Każdy ekran obsługuje **loading / empty / error**, nie tylko happy path.

- **Ładowanie:** skeleton w układzie docelowego ekranu, nigdy przez
  podmianę `innerHTML`.
- **Pusto:** Ordlak w stanie `sleep` plus jedno zdanie instrukcji.
  Pusta lista bywa dobrą wiadomością i nie ma po co świecić.
- **Błąd:** mówi **co** się stało i **co zrobić**. Nie przeprasza i nie
  jest ogólnikowy.
- **Brak połączenia z Pi:** Ordlak przechodzi w `alert`, a wskaźnik
  w stopce paska bocznego nazywa powód.
- **401:** powrót do logowania z komunikatem „Sesja wygasła".

## 10. Reguła nadrzędna: zero przycisków-widm

Każdy element interfejsu musi mieć realne pokrycie w backendzie. Jeśli
makieta pokazuje przycisk, dla którego nie ma endpointu — **nie budujemy
go**, tylko odnotowujemy brak. Przykłady z tego redesignu:

- kafel „Niskie stany" zastąpiony „Rozjazdem stanów", bo Magazyn nie ma
  już progów ani SKU — ilość wisi wprost na ofercie i wpisuje się ją
  ręcznie, więc progu nie ma z czym porównać;
- karta wyniku asystenta na mobile nie ma „Wstaw do oferty", bo wszystkie
  narzędzia Ordlaka na Pi są **tylko do odczytu** — daje za to „Kopiuj"
  i „Udostępnij", które działają;
- mikrofon w polu asystenta pokazuje się wyłącznie tam, gdzie da się
  nagrywać (PWA z Web Speech API).
