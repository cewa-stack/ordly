# Branding - ORDLY

Oficjalna nazwa projektu: **ORDLY**. Żadne wcześniejsze nazwy projektu
nie mogą pojawiać się w kodzie, dokumentacji ani interfejsie użytkownika.

## Nazewnictwo

| Element | Oficjalna nazwa |
|---|---|
| Projekt | ORDLY |
| Bot Telegram | ORDLY |
| Panel WWW | ORDLY Dashboard |
| Backend | ORDLY Core |
| Plugin System | ORDLY Plugins |
| AI (asystent) | Ordlak |
| CLI | ORDLY CLI |
| API | ORDLY API |
| Database | ORDLY Database |

## Paleta kolorów — "Nokturn"

Obowiązuje od redesignu Nokturn (2026-09). Zastępuje wcześniejszą limonkę
`#C6FF00` na `#111111`, która **nie jest już używana nigdzie w produkcie**.

Źródłem prawdy dla wartości jest kod, nie ten plik:
`desktop/src/renderer/src/theme/global.css` oraz `mobile/src/theme/colors.ts`.
Poniżej wyciąg dla materiałów marki.

### Sygnały (wspólne dla wszystkich powierzchni)

| Rola | Hex | Znaczenie |
|---|---|---|
| Teal (akcja, „teraz") | `#5FD9CC` | coś dzieje się w tej chwili |
| Teal marki | `#3EAAAF` | logo, akcenty marki |
| Teal głęboki | `#1F7D80` | wypełnienia, gradienty |
| Koral | `#FF8563` | czeka na użytkownika |
| Bursztyn | `#F5C065` | kanał Amazon |
| Fiolet | `#A79BFF` | kanał OLX |

**Zasada:** teal świeci tylko tam, gdzie coś dzieje się teraz. Koral —
gdy coś czeka na użytkownika. Na jednym ekranie świecą najwyżej dwa punkty.

### Atmosfera nocna (desktop zawsze, mobile 20:00–6:00)

| Rola | Hex |
|---|---|
| Tło okna | `#060D0C` |
| Tło obszaru roboczego | `#0A1413` |
| Karta / panel | `#101D1B` |
| Karta w karcie | `#162724` |
| Tekst | `#EAF3EF` |
| Tekst drugorzędny | `#93A9A3` |
| Tekst trzeciorzędny | `#6F8882` |

### Atmosfera dzienna (tylko mobile, 6:00–20:00)

| Rola | Hex |
|---|---|
| Tło | `#EFF3F0` |
| Karta | `#FFFFFF` |
| Karta w karcie | `#E6EDE9` |
| Akcent | `#12706F` |
| Tekst | `#0F1A17` |
| Tekst drugorzędny | `#5B6B66` |
| Tekst trzeciorzędny | `#64746E` |

Desktop **nie ma** wariantu dziennego — stoi w jednym miejscu, przy stałym
oświetleniu, a dwa warianty to dwa razy więcej powierzchni do utrzymania.

## Typografia

| Krój | Rola |
|---|---|
| Bricolage Grotesque 700 | tytuł ekranu, powitanie, liczba na kaflu, nagłówek panelu |
| Instrument Sans 400/500/600 | treść, wiersze list |
| JetBrains Mono 500/600 | cyfry, numery, godziny, etykiety wersalikami |

Bricolage **wyłącznie** w rolach wyróżnionych — nigdy w wierszu listy.
Kroje ładują się lokalnie z bundla (`@fontsource*` na desktopie,
`@expo-google-fonts/*` na mobile), nigdy z CDN.

## Maskotka — Ordlak

Ordlak jest **wskaźnikiem stanu systemu**, nie ozdobą. Sześć stanów, każdy
z wyzwalaczem w danych: `idle`, `sync`, `think`, `happy`, `alert`, `sleep`.
Stan, którego nie da się powiązać ze zdarzeniem w systemie, nie powstaje.

Od redesignu Nokturn maskotka jest **komponentem SVG**, nie plikiem PNG:
`desktop/src/renderer/src/components/Ordlak.tsx` i
`mobile/src/components/Ordlak.tsx`. Dawne pliki `mascot_*.png` zostały
usunięte — nie należy ich przywracać ani używać w nowych materiałach.

## Logo

Pliki logo znajdują się w [assets/branding/](../assets/branding/).
Logo jest używane w: Telegram, Panel WWW, dokumentacja, README, GitHub.
Podmiana logo polega wyłącznie na zastąpieniu plików w tym katalogu -
kod i dokumentacja odwołują się do nich po stałych nazwach
(`logo.png`, `logo.svg`, `avatar.png`, `favicon.ico`).

## Komunikaty

Każdy komunikat skierowany do użytkownika używa nazwy ORDLY, np.:

> ORDLY został uruchomiony.
