# ORDLY — 13 września 2026: powiadomienia na nowym telefonie, poczta i przegląd błędów

**Co naprawia ta paczka (najważniejsze):**

1. **Telefon: nie było wejścia do Ustawień** — ekran z włączaniem powiadomień
   istniał, ale od przebudowy aplikacji mobilnej (26 sierpnia) nic do niego nie
   prowadziło. Na nowym telefonie nie dało się więc włączyć powiadomień ani
   wysłać testowego. Teraz w prawym górnym rogu jest **zębatka**.
2. **Test powiadomienia mówi prawdę** — wcześniej „Wysłano do N urządzeń"
   liczyło wpisy w bazie, razem z martwą subskrypcją starego telefonu. Teraz
   liczy tylko urządzenia, które faktycznie przyjęły powiadomienie, a martwe
   subskrypcje usuwa i o tym mówi. Test nie jest też wyciszany po 22:00.
3. **„Skrzynka nie odpowiedziała"** — komunikat zawsze kazał sprawdzać hasło,
   niezależnie od prawdziwego powodu. Teraz pokazuje **dosłowny powód odmowy
   z serwera Gmail** (np. złe hasło aplikacji albo limit połączeń). Połączenie
   jest też zamykane po nieudanym logowaniu (wcześniej zostawało otwarte, a
   Gmail pozwala na 15 naraz). W Ustawieniach desktopu doszedł przycisk
   **„Sprawdź logowanie"**.
4. **Godziny w aplikacjach były cofnięte o 2 godziny** (zimą o 1) — API
   wysyłało czas bez strefy, a aplikacje czytały go jako czas lokalny.
5. **„Dziś" liczone od północy w Polsce**, nie w UTC (ekran Start, Statystyki,
   Ordlak). **Anulowane zamówienia nie liczą się już do przychodu.**
   „Ostatnia synchronizacja" pokazuje polską godzinę.
6. **Desktop, Zamówienia:** lista miała tylko 20 ostatnich pozycji (teraz 100);
   „Oznacz jako spakowane" było aktywne dla wysłanych i anulowanych zamówień
   i cofało ich status na Allegro — teraz jest zablokowane.
   **„Oznacz jako spakowane" ustawia teraz na Allegro status „Gotowe do
   wysyłki"** (wcześniej „W realizacji", przez co spakowane zamówienie dalej
   wisiało jako „czeka na spakowanie"). Filtry: Do spakowania · Gotowe do
   wysyłki · Wysłane. Anulowane zamówienia nie liczą się już do „do spakowania".
7. **Desktop, bezpieczeństwo:** link z treści maila mógł otworzyć w systemie
   dowolny protokół (np. plik z udziału sieciowego). Teraz tylko `http`,
   `https` i `mailto`, a okno aplikacji nie da się przenawigować na obcą stronę.
8. **Telefon, Zamówienia:** filtr „Pakowanie" był zawsze pusty, a oś statusu
   w szczegółach znikała dla zamówień w realizacji.
9. **„Dziś w systemie"** nie jest już zapchane wpisami „Start/Koniec
   synchronizacji" (powstają co minutę).

10. **Dane osobowe usunięte z GitHuba** — przykładowe maile w testach
    zawierały prawdziwe dane kupujących (loginy, nazwiska, telefony, e-maile,
    paczkomaty) i Twoje (imię, nazwisko, login, adres zwrotów, e-mail sklepu).
    Zostały zanonimizowane, a **historia repozytorium została przepisana**, żeby
    żadna stara wersja ich nie zawierała.

**Bez migracji bazy.** Commit i push na GitHub są już zrobione.

---

## CZĘŚĆ A — Raspberry Pi (przez SSH)

> **Uwaga: tym razem NIE używaj `git pull`.** Historia repozytorium na GitHubie
> została przepisana (usunięcie danych osobowych), więc `git pull` zatrzyma się
> z błędem o rozbieżnych gałęziach. Zamiast tego Pi dostaje dokładną kopię
> wersji z GitHuba (krok A3). `.env`, baza danych, logi i kopie zapasowe są poza
> Gitem — nie zostaną ruszone.

### A1. Połącz się i wejdź do backendu

```bash
ssh cewastack2@cewastack2
```

```bash
cd ~/ordly/backend
```

### A2. Sprawdź, czy na Pi nie ma lokalnych zmian w kodzie

```bash
git status --short
```

Jeśli pokaże zmienione pliki, cofnij je (nie rusza `.env`):

```bash
git restore .
```

### A3. Pobierz, zsynchronizuj zależności i zrestartuj

**Migracji nie ma** — pomiń `alembic upgrade`.

```bash
git fetch origin
```

```bash
git reset --hard origin/main
```

Ostatnia linia ma zaczynać się od `HEAD is now at` i opisem commita o danych
osobowych.

```bash
uv sync
```

```bash
sudo systemctl restart ordly
```

```bash
sudo systemctl status ordly --no-pager
```

Ma być `active (running)`.

---

## CZĘŚĆ B — poczta: zobacz prawdziwy powód odmowy logowania

Dotyczy błędu „Skrzynka nie odpowiedziała" po kliknięciu Synchronizuj.

### B1. Sprawdź powód (w aplikacji desktopowej, po CZĘŚCI A)

Ustawienia → wiersz **Skrzynka IMAP** → **Sprawdź logowanie**.

- **„Logowanie do skrzynki działa"** — gotowe, nic więcej nie rób.
- **`[AUTHENTICATIONFAILED] Invalid credentials`** — hasło aplikacji Google
  przestało działać (dzieje się tak m.in. po zmianie hasła do konta Google
  albo po przeglądzie bezpieczeństwa konta, np. przy logowaniu na nowym
  telefonie). Przejdź do B2.
- **`Too many simultaneous connections`** — hasło jest dobre, Gmail ma chwilowo
  za dużo otwartych połączeń. Odczekaj 10 minut i sprawdź ponownie.

### B2. Wygeneruj nowe hasło aplikacji (na komputerze)

Zaloguj się w przeglądarce na konto Gmail, z którego ORDLY czyta pocztę, i
otwórz:

```
https://myaccount.google.com/apppasswords
```

Utwórz nowe hasło (nazwa dowolna, np. `ORDLY`) i skopiuj 16 znaków.

### B3. Wpisz je na Pi (przez SSH)

```bash
nano ~/ordly/backend/.env
```

Znajdź linię `IMAP_PASS=` i wklej nowe hasło zamiast starego (bez spacji
i cudzysłowów). Jeśli `SMTP_USER` to ten sam adres co `IMAP_USER`, podmień
także `SMTP_PASS=` — inaczej przestanie działać wysyłka maili do hurtowni.

Zapisz: `Ctrl+O`, `Enter`, wyjdź: `Ctrl+X`.

```bash
sudo systemctl restart ordly
```

Wróć do B1 — ma pojawić się „Logowanie do skrzynki działa".

---

## CZĘŚĆ C — telefon: nowa wersja aplikacji (PWA)

> **Sam `git pull` na Pi NIE aktualizuje aplikacji na telefonie.** Bez tego
> kroku zębatki z Ustawieniami nie będzie.

### C1. Zbuduj aplikację mobilną (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom\mobile
```

```bash
npx expo export -p web
```

Trwa 1–2 minuty. Efekt trafia do `mobile\dist\`.

### C2. Spakuj i wyślij na Pi

Uruchom z katalogu `mobile`. **Nie używaj `Compress-Archive`** — gubi bit
wykonywalności na katalogach.

```bash
tar -czf mobile-dist.tgz -C dist .
```

```bash
scp mobile-dist.tgz cewastack2@cewastack2:~/
```

Upewnij się, że plik doleciał:

```bash
ssh cewastack2@cewastack2 "ls -lh ~/mobile-dist.tgz"
```

Ma pokazać kilka megabajtów. Jeśli `No such file` — **zatrzymaj się tutaj**.

### C3. Podmień paczkę na Pi

```bash
ssh cewastack2@cewastack2 "grep WEB_APP_DIST_PATH ~/ordly/backend/.env"
```

Odpowiedź to `WEB_APP_DIST_PATH=/home/cewastack2/ordly/webapp_dist`. Podmień
zawartość TEGO katalogu:

```bash
ssh cewastack2@cewastack2 "rm -rf ~/ordly/webapp_dist/* && tar -xzf ~/mobile-dist.tgz -C ~/ordly/webapp_dist && chmod -R a+rX ~/ordly/webapp_dist && rm ~/mobile-dist.tgz && sudo systemctl restart ordly"
```

---

## CZĘŚĆ D — nowy telefon: włącz powiadomienia

### D1. Tailscale na nowym telefonie

Aplikacja **Tailscale** musi być zainstalowana i zalogowana na to samo konto
co wcześniej — bez tego adres ORDLY się nie otworzy.

### D2. Zainstaluj ORDLY na ekranie początkowym

Na iPhonie powiadomienia działają **wyłącznie** z ikony na ekranie
początkowym, nie z karty Safari.

1. Otwórz w **Safari** adres ORDLY (ten sam, co w aplikacji desktopowej).
2. Udostępnij → **Do ekranu początkowego**.
3. Otwórz ORDLY **z ikony** i zaloguj się.

Jeśli ikona była dodana przed CZĘŚCIĄ C, zamknij aplikację do końca i otwórz
ponownie, żeby pobrała nową wersję.

### D3. Włącz i przetestuj

1. Stuknij **zębatkę** w prawym górnym rogu.
2. **Powiadomienia push** → **Włącz powiadomienia** → pozwól na powiadomienia.
3. **Wyślij testowe powiadomienie.**

Pod przyciskiem pojawi się np. „Wysłano na 1 urządzenie. Usunięto 1 wygasłą
subskrypcję (np. ze starego telefonu)." — a powiadomienie przyjdzie na ekran.

Jeśli nie przychodzi mimo „Wysłano": Ustawienia iPhone'a → Powiadomienia →
ORDLY → Zezwalaj na powiadomienia.

---

## CZĘŚĆ E — nowy `.exe` (na komputerze)

Zamknij działającą aplikację ORDLY, potem:

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm run dist
```

Zainstaluj `desktop\release\ORDLY-Setup-0.1.0.exe`.

---

## CZĘŚĆ F — sprawdzenie

- **Godziny** przy zamówieniach, mailach i na liście „Dziś w systemie" zgadzają
  się z zegarkiem (wcześniej były o 2 godziny wcześniejsze).
- **Start → Dziś w systemie**: bez „Start/Koniec synchronizacji", tylko
  dzisiejsze zdarzenia.
- **Synchronizuj** przy niedziałającej poczcie: wskaźnik mówi „Zamówienia
  aktualne · poczta niedostępna", a toast podaje powód z serwera.
- **Zamówienia**: okruszek „ostatnie N" pokazuje realną liczbę; przy wysłanym
  zamówieniu „Oznacz jako spakowane" jest wyszarzone.
- **Telefon → Zamówienia → Pakowanie**: pokazuje zamówienia w realizacji.
