# ORDLY — 22 września 2026: nowe ikony i powiadomienia „Nokturn"

Zastępuje `wdrozenie_2026-09-22-ikony.md` — tamta instrukcja nie była
jeszcze wgrywana, a ta obejmuje ją w całości.

**Co zmienia ta paczka:**

1. **Nowa ikona** — Ordlak na wprost, wyśrodkowany na osi twarzy, na
   ciemnozielonym tle. Na iPhonie (ekran główny i każde powiadomienie)
   i na Windowsie (`.exe`, pasek zadań, pulpit).
2. **Liczba na ikonie aplikacji = „Wymaga uwagi" z ekranu Start**
   (Do spakowania + Dyskusje + Zwroty). Dotąd każde powiadomienie
   ustawiało ją po swojemu — dyskusja wbijała na sztywno 1, nowe
   zamówienie jej nie ruszało.
3. **Poranny raport o 9:00** zamiast wieczornego przypomnienia na
   telefonie. Mówi o paczkach, dyskusjach i zwrotach naraz, otwiera ekran
   Start. Naprawia błąd: godzina „najstarsze od…" była w UTC, czyli latem
   cofnięta o 2 h.
4. **Anulowanie** — bez loginu kupującego, z kwotą, dalej ciche.
5. **Allegro Lokalnie „doręczono / anulowano"** przychodzi po cichu.
   Zwroty z Lokalnie dzwonią jak dotąd.
6. **Test powiadomień** ma tytuł „Powiadomienia działają".
7. **Ordlak na desktopie śpi do 7:00** — tak jak trwa cisza powiadomień.
8. **Telefon liczy „Do spakowania" tak samo jak desktop.** Wcześniej
   wliczał paczki już spakowane i zamówienia anulowane z etapem NEW.

**Co zostaje bez zmian:** Telegram — dalej dostaje przypomnienie
o 20:00 i wszystkie powiadomienia w dotychczasowej formie.

**Bez migracji bazy i bez nowych zależności na Pi.**

> **Uwaga o godzinie przypomnienia.** Stary podgląd powiadomień opisywał
> przypomnienie o pakowaniu jako „raz dziennie o 9:00". W rzeczywistości
> wychodziło o **20:00**. Po tej paczce na telefon przychodzi poranny
> raport o 9:00, a wieczornego pusha już nie ma. Jeśli chcesz mieć oba —
> daj znać, to jedna linijka.

---

## Kolejność: Pi → telefon → desktop

Najpierw backend: nowa aplikacja na telefonie otwiera poranny raport pod
adresem `/start`, a plakietkę liczy Pi.

---

## CZĘŚĆ A — scal i wypchnij (na komputerze)

Na GitHubie jest dziś pierwsza wersja ikony iOS (commit `b5cedb3` — ta
nierówna). Ta paczka ją zastępuje. Jeśli zdążyłeś ją wgrać na telefon,
krok C4 i tak ją podmieni.

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

Na liście zmian zobaczysz usunięte pliki `bot_ordlak/mascot_*.png`
i `mascot_*-removebg-preview.png` — tych nie usuwałem ja i nie są częścią
tej paczki. Nic w kodzie ich nie używa.

```bash
git checkout main
```

```bash
git merge nokturn-powiadomienia
```

Ma napisać `Fast-forward`. Jeśli zobaczysz `CONFLICT` — zatrzymaj się
i wklej mi output.

```bash
git push
```

---

## CZĘŚĆ B — Raspberry Pi: backend (przez SSH)

### B1. Połącz się

```bash
ssh cewastack2@cewastack2
```

```bash
cd ~/ordly/backend
```

### B2. Kopia bazy

Migracji nie ma, ale kopia to dwie sekundy:

```bash
cp data/ordly.db ~/ordly-przed-powiadomieniami-2026-09-22.db
```

### B3. Lokalne zmiany na Pi

```bash
git status --short
```

Jeśli pokaże zmienione pliki, cofnij je (nie rusza `.env` ani `data/`):

```bash
git restore .
```

### B4. Pobierz kod i zrestartuj

```bash
git pull
```

```bash
uv sync
```

```bash
sudo systemctl restart ordly
```

```bash
sudo systemctl status ordly --no-pager | head -3
```

Ma być `active (running)`.

### B5. Sprawdź, że poranny raport jest zaplanowany

```bash
journalctl -u ordly --since "2 min ago" | grep -i "poranny raport\|error\|traceback"
```

Ma się pojawić linia **`Zarejestrowano poranny raport push (9:00)`**.
Jeśli jej nie ma albo widać `error` / `traceback` — wklej mi output.

---

## CZĘŚĆ C — telefon: nowa paczka PWA

### C1. Zbuduj (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom\mobile
```

```bash
npx expo export -p web
```

```bash
dir dist\apple-touch-icon.png
```

Ma pokazać plik. Jeśli `File Not Found` — zatrzymaj się tutaj.

### C2. Spakuj i wyślij

**Nie używaj `Compress-Archive`** — gubi bit wykonywalności na katalogach.

```bash
tar -czf mobile-dist.tgz -C dist .
```

```bash
scp mobile-dist.tgz cewastack2@cewastack2:~/
```

### C3. Podmień paczkę na Pi

```bash
ssh cewastack2@cewastack2 "grep WEB_APP_DIST_PATH ~/ordly/backend/.env"
```

Ma pokazać `/home/cewastack2/ordly/webapp_dist`. Jeśli coś innego —
podmień ścieżkę w komendzie niżej.

```bash
ssh cewastack2@cewastack2 "rm -rf ~/ordly/webapp_dist/* && tar -xzf ~/mobile-dist.tgz -C ~/ordly/webapp_dist && chmod -R a+rX ~/ordly/webapp_dist && rm ~/mobile-dist.tgz && sudo systemctl restart ordly"
```

### C4. Podmień ikonę na iPhonie

> ⚠️ **iOS zapamiętuje ikonę w chwili dodania do ekranu głównego i sam jej
> nie odświeża.** Bez tego kroku zostanie stara — także w powiadomieniach.

1. Przytrzymaj ikonę ORDLY → **Usuń aplikację** → **Usuń z ekranu
   początkowego**. (Usuwa tylko skrót — dane zostają na Pi.)
2. **Safari** → `https://cewastack2.tail7f5a20.ts.net`.
3. **Udostępnij** → **Do ekranu początkowego** → **Dodaj**.
4. Otwórz ORDLY z nowej ikony, zaloguj się, jeśli poprosi.
5. **Włącz powiadomienia ponownie**: Ustawienia w ORDLY → Powiadomienia.
   Dla iOS to nowa aplikacja — stara subskrypcja nie przechodzi.

Jeśli przy „Dodaj do ekranu początkowego" widać jeszcze starą ikonę:
Ustawienia iPhone'a → Safari → **Wyczyść historię i dane witryn**, potem
krok 2 od nowa.

### C5. Test

Ustawienia w ORDLY → **Wyślij test**. Ma przyjść powiadomienie:

- tytuł **„Powiadomienia działają"**,
- z nową ikoną (Ordlak na wprost),
- a liczba na ikonie aplikacji ma się zgadzać z sumą trzech kafli na
  ekranie Start (Do spakowania + Dyskusje + Zwroty).

Karta w Ustawieniach pokaże też, do ilu urządzeń doszło. Martwa
subskrypcja starej instalacji zostanie przy tym usunięta sama.

---

## CZĘŚĆ D — desktop: nowy `.exe`

Instalator jest **już zbudowany** z tej paczki:
`desktop\release\ORDLY-Setup-0.1.0.exe`. Zamknij działające ORDLY
i zainstaluj go.

Jeśli wolisz zbudować sam:

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm install
```

```bash
npm run dist
```

Jeśli po instalacji przypięta ikona na pasku zadań albo skrót na pulpicie
jest stary — to pamięć podręczna Windowsa: odepnij i przypnij ponownie
z menu Start, a skrót na pulpicie usuń i przeciągnij nowy z menu Start.

---

## Sprawdzenie w kolejnych dniach

- **Jutro o 9:00:** poranny raport, jeśli coś czeka. Kliknięcie otwiera
  ekran Start. Godzina „najstarsze od…" ma się zgadzać z tym, co widzisz
  w aplikacji (wcześniej była o 2 h wcześniejsza).
- **O 20:00:** push o pakowaniu już nie przyjdzie. Telegram — przyjdzie
  jak zawsze.
- **Przy każdym powiadomieniu:** liczba na ikonie = Do spakowania +
  Dyskusje + Zwroty z ekranu Start. Gdy Allegro chwilowo nie odpowiada,
  liczba zostaje bez zmian (nie spada do zaniżonej).
- **Po spakowaniu paczki na desktopie** znika ona z „Do spakowania" także
  na telefonie.

---

## Gdyby coś poszło nie tak

```bash
journalctl -u ordly -f
```

Powrót do stanu sprzed paczki — jedna komenda na raz:

```bash
sudo systemctl stop ordly
```

```bash
cd ~/ordly/backend
```

```bash
git checkout b5cedb3
```

```bash
uv sync
```

```bash
sudo systemctl start ordly
```

Baza się nie zmieniała, więc kopii z B2 nie trzeba przywracać. Po takim
cofnięciu napisz do mnie — trzeba jeszcze wrócić z „odłączonego" stanu
gita (`git checkout main`) i przywrócić poprzednią paczkę PWA.

---

## Pliki

| Plik | Do czego |
|---|---|
| `backend/src/app/services/attention_service.py` | „Wymaga uwagi" — plakietka i raport |
| `backend/src/app/infrastructure/webpush/push_payload.py` | treści powiadomień |
| `backend/docs/podglad-powiadomien-push.html` | podgląd wszystkich powiadomień po zmianach |
| `desktop/build/make-icon.mjs` | JEDNO źródło wszystkich ikon (iPhone, PWA, `.ico`) |
