# ORDLY — wdrożenie zmian z 4 sierpnia 2026

Ta instrukcja przeprowadza przez trzy rzeczy naraz:

1. **naprawę Dyskusji** (wątki nie ładowały się po kliknięciu),
2. **naprawę Poczty** (skrzynka była pusta i nic o tym nie mówiła),
3. **nową aplikację desktopową** — pełny redesign + plik `.exe` na laptopa.

Punkty 1 i 2 wymagają aktualizacji backendu na Raspberry Pi.
Punkt 3 robi się w całości na komputerze.

> **Kolejność ma znaczenie.** Najpierw CZĘŚĆ A (Pi), potem CZĘŚĆ B (komputer).
> Nowa aplikacja pyta backend o rzeczy, których stara wersja na Pi jeszcze
> nie zna — bez aktualizacji Pi ekran Poczty pokaże błąd 404.

---

## Co dokładnie było zepsute

### Dyskusje — wątek nie chciał się otworzyć

Allegro zwraca w wątkach wiadomości, w których `author.login` jest ustawione
na `null` (wiadomości systemowe albo zanonimizowany kupujący). Kod czytał to
przez `author.get("login", "nieznany")` — a wartość domyślna w `.get()` działa
**tylko wtedy, gdy klucza nie ma**. Klucz był, tylko pusty, więc `None`
przelatywało dalej i cały endpoint `/api/v1/issues/{id}/messages` zwracał
błąd 422. Lista dyskusji działała, ale każde kliknięcie w wątek kończyło się
niczym.

Sprawdzone na żywym Pi przed poprawką:

```
HTTP 422 — "1 validation error for IssueMessageOut / author_login /
Input should be a valid string [input_value=None]"
```

Poprawka: mapper czyta wszystkie pola przez `or`, a wiadomości bez loginu
dostają czytelną nazwę (`Allegro`, `Ty`, `Kupujący`) zamiast `nieznany`.

### Poczta — pusto i bez wyjaśnienia

`/api/v1/mail/messages` zwracał pustą listę, a aplikacja pokazywała „Brak maili
do pokazania” — dokładnie to samo, co gdyby maile po prostu jeszcze nie
przyszły. Nie było jak odróżnić „IMAP nie jest skonfigurowany na Pi” od
„skonfigurowany, ale skrzynka pusta” od „logowanie IMAP odrzucone”.

Poprawka to trzy rzeczy:

- nowy `GET /api/v1/mail/status` — mówi, czy IMAP jest włączony, jakie konto
  obserwuje, ilu nadawców śledzi i ile maili leży w bazie,
- nowy `POST /api/v1/mail/sync` — ręczne sprawdzenie skrzynki, które **zwraca
  błąd**, zamiast go połknąć (cykliczny job dalej połyka, bo nie ma komu go
  pokazać),
- ekran Poczty w aplikacji pokazuje konkretny powód i konkretną komendę do
  wpisania na Pi.

---

## CZĘŚĆ A — na Raspberry Pi (przez SSH)

### A1. Połącz się z Pi

Na komputerze, w terminalu:

```bash
ssh cewastack2@cewastack2
```

### A2. Wejdź do katalogu backendu

```bash
cd ~/ordly/backend
```

### A3. Sprawdź, czy nie ma lokalnych zmian blokujących pobranie

```bash
git status --short
```

Jeśli pokaże jakiekolwiek zmodyfikowane pliki (linie zaczynające się od `M`),
cofnij je — inaczej `git pull` odmówi:

```bash
git restore .
```

### A4. Pobierz nową wersję

```bash
git pull
```

### A5. Zainstaluj zależności (na wypadek zmian)

```bash
uv sync
```

Jeśli `uv sync` twierdzi, że wszystko jest aktualne, a coś potem nie działa:

```bash
rm -rf .venv && uv sync
```

### A6. Skonfiguruj skrzynkę IMAP (tylko jeśli chcesz mieć Pocztę)

Otwórz plik konfiguracyjny:

```bash
nano ~/ordly/backend/.env
```

Znajdź (albo dopisz na końcu) te linie i uzupełnij swoimi danymi:

```
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=twoj.adres@gmail.com
IMAP_PASS=haslo-aplikacji-z-google
MAIL_WATCH_SENDERS=allegro.pl,olx.pl
```

**Uwaga do `IMAP_PASS`:** Gmail i iCloud **nie przyjmą zwykłego hasła do
konta**. Potrzebujesz „hasła aplikacji”:
Google → Konto → Bezpieczeństwo → Weryfikacja dwuetapowa → Hasła aplikacji →
wygeneruj nowe. To ciąg 16 znaków — wklej go bez spacji.

Zapisz i wyjdź z edytora: `Ctrl+O`, `Enter`, potem `Ctrl+X`.

### A7. Zrestartuj usługę

```bash
sudo systemctl restart ordly
```

### A8. Sprawdź, czy wstała

```bash
sudo systemctl status ordly --no-pager
```

Szukasz linii `Active: active (running)`. Jeśli jest `failed`, zobacz logi:

```bash
journalctl -u ordly -n 50 --no-pager
```

### A9. Sprawdź, czy nowe endpointy odpowiadają

Najpierw zaloguj się po token (podmień hasło, jeśli zmieniałeś):

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
```

Skopiuj wartość `token` z odpowiedzi i wklej ją poniżej zamiast `TU_TOKEN`:

```bash
curl -s http://localhost:8000/api/v1/mail/status -H "Authorization: Bearer TU_TOKEN"
```

Poprawna odpowiedź wygląda mniej więcej tak:

```json
{"configured":true,"host":"imap.gmail.com","user_masked":"tw***@gmail.com",
 "watch_senders":["allegro.pl","olx.pl"],"message_count":0,"last_received_at":null}
```

`"configured":false` oznacza, że `.env` nadal nie ma kompletu `IMAP_HOST` +
`IMAP_USER` + `IMAP_PASS`. Wróć do kroku A6.

### A10. Wymuś pierwsze pobranie maili

```bash
curl -s -X POST http://localhost:8000/api/v1/mail/sync -H "Authorization: Bearer TU_TOKEN"
```

- `{"new_count":3,"configured":true}` — działa, pobrało 3 maile.
- `{"new_count":0,"configured":true}` — połączenie OK, ale w skrzynce nie ma
  nic od obserwowanych nadawców z ostatnich 7 dni.
- Błąd 502 z treścią „Logowanie IMAP odrzucone…” — złe `IMAP_USER`/`IMAP_PASS`
  (najczęściej: zwykłe hasło zamiast hasła aplikacji).

### A11. Sprawdź, czy wątki dyskusji już się otwierają

```bash
curl -s http://localhost:8000/api/v1/issues -H "Authorization: Bearer TU_TOKEN"
```

Weź `external_id` pierwszej dyskusji z odpowiedzi i wklej poniżej zamiast `TU_ID`:

```bash
curl -s http://localhost:8000/api/v1/issues/TU_ID/messages -H "Authorization: Bearer TU_TOKEN"
```

Ma wrócić lista wiadomości. Jeśli nadal widzisz `422` i `validation error` —
`git pull` nie zaciągnął poprawki, wróć do kroku A3.

Zakończ sesję SSH:

```bash
exit
```

---

## CZĘŚĆ B — na komputerze (aplikacja desktopowa)

### B1. Wejdź do katalogu aplikacji

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

### B2. Zainstaluj zależności

Doszły trzy paczki z krojami pism (Space Grotesk, Inter, JetBrains Mono) oraz
`electron-builder` do robienia pliku `.exe`.

```bash
npm install
```

### B3. Uruchom aplikację w trybie deweloperskim (szybki test)

```bash
npm run dev
```

Aplikacja otworzy się w osobnym oknie. Zamknij ją, gdy skończysz sprawdzać.

### B4. Zbuduj plik .exe

```bash
npm run dist
```

Budowanie trwa kilka minut. Efekt trafia do katalogu `desktop\release\`:

- **`ORDLY-Setup-0.1.0.exe`** — instalator. Tworzy skrót na pulpicie i wpis
  w menu Start, da się odinstalować przez Panel sterowania. To jest wersja,
  której chcesz na co dzień.
- **`ORDLY-0.1.0-portable.exe`** — wersja przenośna. Odpalasz plik i już,
  bez instalacji. Wygodna na pendrive albo do przetestowania na drugim
  komputerze.

### B5. Zainstaluj i uruchom

Kliknij dwukrotnie `ORDLY-Setup-0.1.0.exe`.

> **Windows pokaże ostrzeżenie „Nieznany wydawca” / SmartScreen.** To normalne
> — aplikacja nie jest podpisana certyfikatem Authenticode (płatny, wystawiany
> przez zewnętrzną firmę). Kliknij **Więcej informacji → Uruchom mimo to**.

### B6. Zaloguj się

Przy pierwszym uruchomieniu aplikacja poprosi o adres serwera i dane:

- **Adres serwera:** `https://cewastack2.tail7f5a20.ts.net`
  (koniecznie `https://`, nie `http://` — Tailscale serwuje ORDLY po HTTPS)
- **Login:** `admin`
- **Hasło:** to z `ORDLY_ADMIN_PASSWORD` w `.env` na Pi (domyślnie `admin`)

Token zapisuje się zaszyfrowany (Windows DPAPI, powiązany z Twoim kontem) —
kolejne uruchomienia wchodzą od razu do aplikacji.

---

## Co nowego w aplikacji

### Nowe ekrany

- **Start** — hero mówi, co jest najpilniejsze **teraz** (zamówienia do
  spakowania → czekający klienci → niski stan), trzy karty skrótów z dużymi
  liczbami, oś „Dziś w systemie” z prawdziwym dziennikiem zdarzeń z Pi.
  Pasek statystyk na górze pojawia się **wyłącznie** na tym ekranie.
- **Ustawienia** — stan Pi, stan tokenu Allegro, stan skrzynki IMAP, edycja
  progów niskiego stanu per produkt, ręczna kopia zapasowa bazy, wylogowanie.

### Nowe działające funkcje

- **Oznacz jako spakowane / wysłane** — zapisuje status **najpierw na Allegro**,
  dopiero potem lokalnie. Jeśli Allegro odmówi, aplikacja mówi to wprost
  i nie udaje, że zamówienie jest obsłużone.
- **Akcje zbiorcze** — zaznaczasz wiele zamówień, oznaczasz jednym kliknięciem.
- **Filtry i sortowanie** w Zamówieniach i Magazynie — realnie zmieniają listę.
- **Ctrl+K** — wyszukiwanie po numerze zamówienia, nazwie kupującego, SKU
  i nazwie produktu, z przejściem do konkretnego rekordu.
- **Eksport CSV** listy zamówień (średnik + BOM, otwiera się poprawnie
  w polskim Excelu).
- **Nowy produkt** i **historia ruchów magazynowych**.
- **Szablony odpowiedzi** w Dyskusjach — cztery gotowe treści.
- **Zamówienie do hurtowni** wypełnia się samo produktami poniżej progu,
  z policzoną ilością do uzupełnienia.
- **Skróty klawiszowe:** `Ctrl+K` lub `/` — paleta poleceń, `Ctrl+R` —
  synchronizacja, `G` + litera — przejście do ekranu (`G S` Start,
  `G Z` Zamówienia, `G D` Dyskusje, `G M` Magazyn, `G P` Poczta,
  `G W` Zwroty, `G H` Hurtownie, `G T` Statystyki, `G U` Ustawienia).

### Czego świadomie NIE ma

- **Przycisków „Przyjmij / Odrzuć zwrot”.** Przyjęcie zwrotu na Allegro to
  operacja finansowa (zwrot pieniędzy kupującemu). ORDLY pokazuje wszystkie
  zwroty, ich wiek i status, i prowadzi do panelu Allegro — decyzję
  podejmujesz tam, świadomie. Zero przycisków-widmo.
- **Podłączania konta Allegro z poziomu aplikacji.** OAuth Allegro wymaga
  przeglądarki i tunelu do Pi — Ustawienia pokazują stan tokenu i dokładną
  komendę do uruchomienia, zamiast przycisku, który i tak by nie zadziałał.

---

## Rozwiązywanie problemów

### „Nie widzę ORDLY API pod tym adresem”

Pi nie odpowiada. Sprawdź po kolei — jedno polecenie na raz:

```bash
ssh cewastack2@cewastack2 "sudo systemctl status ordly --no-pager"
```

```bash
ssh cewastack2@cewastack2 "sudo ss -ltnp | grep :8000"
```

Jeśli port 8000 zajmuje osierocony proces po ręcznym uruchomieniu:

```bash
ssh cewastack2@cewastack2 "sudo fuser -k 8000/tcp && sudo systemctl restart ordly"
```

### Ekran Poczty pokazuje błąd 404

Na Pi działa jeszcze stara wersja backendu — endpoint `/api/v1/mail/status`
nie istnieje. Wróć do CZĘŚCI A, kroki A4–A7.

### Dyskusje: „403 AccessDenied”

To nie jest błąd kodu. Aplikacja zarejestrowana na `apps.developer.allegro.pl`
nie ma włączonego uprawnienia **„Dyskusje i reklamacje pozakupowe”**. Włącz je
w portalu, a potem zaloguj się ponownie po świeży token — na komputerze:

```bash
ssh -L 53682:localhost:53682 cewastack2@cewastack2
```

i w tej samej sesji:

```bash
cd ~/ordly/backend && uv run python scripts/allegro_login.py
```

### „Oznacz jako spakowane” zwraca błąd 403

Analogicznie: brakuje uprawnienia **`allegro:api:orders:write`** na poziomie
rejestracji aplikacji w portalu Allegro. Sam ponowny login go nie doda —
najpierw trzeba włączyć uprawnienie w portalu, potem powtórzyć `allegro_login.py`.

### `npm run dist` kończy się błędem `EBUSY: resource busy or locked`

Pełna treść to zwykle:

```
⨯ EBUSY: resource busy or locked, rmdir '…\desktop\release\win-unpacked'
```

Znaczy dokładnie tyle: coś trzyma katalog `release\win-unpacked` i Windows nie
pozwala go usunąć. Najczęstsze przyczyny to **uruchomiona aplikacja ORDLY**
(albo z instalatora, albo bezpośrednio z `win-unpacked`) oraz **otwarty
Eksplorator Windows albo terminal, który stoi w tym katalogu**.

Zamknij aplikację i wyjdź terminalem gdzie indziej, a potem:

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
taskkill /IM ORDLY.exe /F
```

```bash
rmdir /s /q release\win-unpacked
```

Teraz `npm run dist` przejdzie.

### Chcę zobaczyć, co dokładnie wywala się w aplikacji

Uruchom ją z włączonymi narzędziami deweloperskimi — w PowerShellu:

```bash
$env:ORDLY_DEVTOOLS=1; & "$env:LOCALAPPDATA\Programs\ORDLY\ORDLY.exe"
```

Otworzy się panel DevTools, a konsola renderera trafi też do terminala.
