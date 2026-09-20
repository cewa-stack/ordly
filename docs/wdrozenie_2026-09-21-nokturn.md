# ORDLY — 21 września 2026: redesign „Nokturn" i Ordlak, który może działać

**Co zmienia ta paczka:**

1. **Nowa warstwa wizualna „Nokturn" w obu aplikacjach.** Głęboka
   zieleń-petrol z jednym źródłem światła, teal jako sygnał „dzieje się
   teraz", koral jako „czeka na Ciebie". Nowe kroje: Bricolage Grotesque,
   Instrument Sans, JetBrains Mono — wszystkie z paczki, bez internetu.
2. **Maskotka Ordlak jest teraz rysunkiem wektorowym, nie zdjęciem.**
   Sześć stanów, każdy z powodem: `sync` przy synchronizacji, `alert` przy
   awarii, `think` gdy generuje odpowiedź, `sleep` w nocy i na pustych
   listach. Osiem plików PNG zniknęło.
3. **Telefon ma dwie atmosfery** — dzienną (6:00–20:00) i nocną, plus
   ręczne nadpisanie w Ustawieniach → „Atmosfera". Desktop zostaje
   wyłącznie nocny.
4. **Nowy pasek zakładek na telefonie:** Start · Zamówienia · **Ordlak** ·
   Magazyn · Poczta. Ordlak to gałka pośrodku, która pokazuje swój stan.
   Dyskusje i Zwroty zeszły z paska — wchodzi się w nie kaflami na
   ekranie Start (i dalej z powiadomień push).
5. **Asystent na telefonie** — pełny czat, ten sam co na desktopie.
6. **Ordlak może teraz coś zrobić, nie tylko doradzić.** Trzy rzeczy:
   wpisać stan na półce, oznaczyć zamówienie jako spakowane/wysłane,
   wysłać odpowiedź w dyskusji.

---

## ⚠️ Jak działają nowe działania Ordlaka — przeczytaj raz

**Model proponuje. Ty zatwierdzasz. Dopiero wtedy coś się zapisuje.**

Ordlak nie ma żadnego narzędzia, które sam wykonuje. Gdy poprosisz go
o zrobienie czegoś, pod odpowiedzią pojawia się **przycisk z opisem, co
dokładnie się stanie**. Dopóki go nie naciśniesz — nic się nie dzieje.

Dwa z trzech działań widzi ktoś poza Tobą:

| Działanie | Kto to zobaczy | Potwierdzenie |
|---|---|---|
| Wpisanie stanu na półce | tylko Ty, w ORDLY | jedno kliknięcie |
| Oznaczenie zamówienia | **kupujący, na Allegro** | osobne okno „na pewno?" |
| Odpowiedź w dyskusji | **kupujący, jako wiadomość** | osobne okno „na pewno?" |

Propozycje **żyją tylko w bieżącej rozmowie**. Po zamknięciu aplikacji
przyciski znikają — celowo. Propozycja sprzed trzech dni („oznacz jako
wysłane") nie ma prawa być jedno kliknięcie od wykonania, bo od tamtej
pory stan mógł się zmienić.

Czego Ordlak nadal **nie** zrobi: nie wyśle maila do hurtowni, nie zmieni
ceny, nie wystawi ani nie zakończy oferty, nie anuluje zamówienia i nie
cofnie statusu.

---

## Dobra wiadomość: **nie ma migracji bazy**

Ta paczka nie dodaje ani nie usuwa żadnej tabeli. Propozycje działań nie
są zapisywane, więc baza zostaje dokładnie taka, jaka jest.

Kopię bazy i tak zrób (krok B2) — to dwie sekundy, a jest jedyną rzeczą,
której nie da się odtworzyć.

---

## Kolejność ma znaczenie: **najpierw Pi, potem aplikacje**

Nowe aplikacje wołają endpoint `POST /api/v1/ordlak/apply`, którego stary
backend nie zna. Jeśli zainstalujesz najpierw `.exe`, przycisk „Oznacz
jako wysłane" odpowie błędem 404, dopóki nie zaktualizujesz Pi.

Odwrotnie jest bezpiecznie: nowy backend ze starą aplikacją działa
normalnie, tylko bez przycisków.

---

## CZĘŚĆ A — commit i push (na komputerze)

Praca siedzi na gałęzi `redesign-nokturn`. Pi ciągnie `main`, więc trzeba
ją scalić.

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

Sprawdź, czy nie ma niezapisanych zmian:

```bash
git status --short
```

Pusto = dobrze. Teraz scal gałąź do `main`:

```bash
git checkout main
```

```bash
git merge redesign-nokturn
```

Ma napisać `Fast-forward` albo zrobić commit scalenia bez konfliktów.
Jeśli zobaczysz `CONFLICT` — **zatrzymaj się** i wklej mi output.

```bash
git push
```

---

## CZĘŚĆ B — Raspberry Pi, backend (przez SSH)

### B1. Połącz się i wejdź do backendu

```bash
ssh cewastack2@cewastack2
```

```bash
cd ~/ordly/backend
```

### B2. Zrób kopię bazy

```bash
cp data/ordly.db ~/ordly-przed-nokturn-2026-09-21.db
```

Sprawdź, że kopia powstała i nie jest pusta:

```bash
ls -lh ~/ordly-przed-nokturn-2026-09-21.db
```

Ma pokazać plik o rozmiarze kilku MB. Jeśli `No such file` albo `0` —
**zatrzymaj się tutaj** i napisz, co pokazało.

### B3. Sprawdź, czy na Pi nie ma lokalnych zmian w kodzie

```bash
git status --short
```

Jeśli pokaże zmienione pliki, cofnij je (nie rusza `.env` ani `data/`):

```bash
git restore .
```

### B4. Pobierz kod i zsynchronizuj zależności

```bash
git pull
```

```bash
uv sync
```

### B5. Restart usługi

Migracji nie ma, więc nie trzeba zatrzymywać bazy — wystarczy restart:

```bash
sudo systemctl restart ordly
```

```bash
sudo systemctl status ordly --no-pager
```

Ma być `active (running)`.

### B6. Sprawdź, że nowy endpoint istnieje

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/api/v1/ordlak/apply
```

Ma pokazać **`401`** — czyli „endpoint jest, ale nie podałeś tokena". To
jest wynik prawidłowy.

`404` znaczy, że backend dalej chodzi na starym kodzie — wróć do B4.

### B7. Sprawdź logi

```bash
journalctl -u ordly --since "2 min ago" | grep -i "error\|traceback"
```

Brak wyniku = dobrze. Jeśli coś się wypisze, wklej mi to.

---

## CZĘŚĆ C — telefon: nowa wersja aplikacji (PWA)

> **Sam `git pull` na Pi NIE aktualizuje aplikacji na telefonie.** Bez tego
> kroku telefon pokaże stary wygląd, stary pasek zakładek i nie będzie
> miał ekranu asystenta.

### C1. Zbuduj aplikację mobilną (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom\mobile
```

```bash
npx expo export -p web
```

Trwa 1–3 minuty (nowe kroje to kilkanaście plików więcej niż zwykle).
Efekt trafia do `mobile\dist\`.

### C2. Spakuj i wyślij na Pi

Uruchom z katalogu `mobile`. **Nie używaj `Compress-Archive`** — gubi bit
wykonywalności na katalogach.

```bash
tar -czf mobile-dist.tgz -C dist .
```

```bash
scp mobile-dist.tgz cewastack2@cewastack2:~/
```

```bash
ssh cewastack2@cewastack2 "ls -lh ~/mobile-dist.tgz"
```

Jeśli `No such file` — zatrzymaj się tutaj.

### C3. Upewnij się, gdzie backend szuka paczki

Nie zakładaj ścieżki — sprawdź ją:

```bash
ssh cewastack2@cewastack2 "grep WEB_APP_DIST_PATH ~/ordly/backend/.env"
```

Ma pokazać `/home/cewastack2/ordly/webapp_dist`. Jeśli pokaże **coś
innego**, podmień ścieżkę w komendzie z C4.

### C4. Podmień paczkę na Pi

```bash
ssh cewastack2@cewastack2 "rm -rf ~/ordly/webapp_dist/* && tar -xzf ~/mobile-dist.tgz -C ~/ordly/webapp_dist && chmod -R a+rX ~/ordly/webapp_dist && rm ~/mobile-dist.tgz && sudo systemctl restart ordly"
```

### C5. Odśwież PWA na telefonie

Zamknij aplikację ORDLY na telefonie **całkowicie** (przesuń w górę
z listy aplikacji) i otwórz ponownie. Sam powrót do niej pokaże starą
wersję z pamięci.

Jeśli po otwarciu dalej widzisz stary wygląd: wejdź w przeglądarce na
`https://cewastack2.tail7f5a20.ts.net`, odśwież z wyczyszczeniem pamięci
(przytrzymaj przycisk odświeżania), a potem dodaj do ekranu głównego
jeszcze raz.

---

## CZĘŚĆ D — nowy `.exe` (na komputerze)

Zamknij działającą aplikację ORDLY, potem:

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm install
```

To nie jest zwykła formalność — doszły trzy paczki z krojami pisma
(`@fontsource-variable/bricolage-grotesque`, `@fontsource/instrument-sans`
i waga 600 JetBrains Mono). Bez tego build się wywali.

```bash
npm run dist
```

Zainstaluj `desktop\release\ORDLY-Setup-0.1.0.exe`.

---

## CZĘŚĆ E — sprawdzenie

### E1. Wygląd (desktop)

- Okno jest ciemnozielone, nie czarne. Tytuł „Start" krojem Bricolage,
  imię w kolorze teal.
- Pasek boczny ma dwie grupy: **GŁÓWNE** i **ZAPLECZE**, aktywna pozycja
  ma pionowy pasek teal po lewej (bez ramki).
- U góry ekranu Start: karta powitalna z maskotką, pod nią pasek
  „Zapytaj Ordlaka", niżej cztery kafle, na dole dwie kolumny.
- W stopce paska bocznego maskotka pokazuje stan i podpisuje go słowami.
- Miniatury ofert w Magazynie **wreszcie się ładują** (wcześniej blokowała
  je polityka bezpieczeństwa okna i każda oferta miała ikonę zastępczą).

### E2. Wygląd (telefon)

- Pasek zakładek: Start · Zamówienia · **Ordlak** · Magazyn · Poczta,
  z wypukłą gałką pośrodku.
- Gdy jakaś dyskusja jest otwarta, gałka ma koralową obwódkę, a maskotka
  robi się koralowa. To jest sygnał „coś czeka".
- Ustawienia → **Atmosfera** → przełącz na „Dzień" i „Noc”. Cały interfejs
  ma się przemalować od razu, bez restartu aplikacji.
- Dyskusje i Zwroty: kafle na ekranie Start.

### E3. Ordlak — odczyt

Wejdź w zakładkę **Ordlak** (telefon) albo ekran **Ordlak** (desktop)
i zapytaj:

> Podsumuj dzisiejszą sprzedaż

Ma odpowiedzieć liczbami z bazy i pokazać pod spodem, z których narzędzi
skorzystał.

### E4. Ordlak — działanie (najważniejszy test)

Zapytaj o coś, co da się zrobić, np.:

> Policzyłem świece, jest ich 12. Wpisz to.

Pod odpowiedzią ma pojawić się **karta z opisem i przyciskiem**
(„Wpisz 12 szt."). Sprawdź po kolei:

1. **Zanim naciśniesz** — wejdź w Magazyn i zobacz, że stan jest stary.
   To potwierdza, że sama propozycja niczego nie zapisała.
2. Naciśnij przycisk. Ma zmienić się w „Zrobione" i pokazać potwierdzenie.
3. Wróć do Magazynu — stan ma być nowy, a w **Historii** przy ofercie
   ma być wpis z powodem **„Ordlak (zatwierdzone w aplikacji)"**.

Teraz test działania widocznego na zewnątrz:

> Nadałem paczkę dla [nazwa kupującego], oznacz ją jako wysłaną

Ma pojawić się przycisk **„Oznacz jako wysłane"**, a po jego naciśnięciu
**osobne okno z pytaniem** i zdaniem „Kupujący zobaczy to od razu i nie
da się tego cofnąć z ORDLY". Dopiero potwierdzenie w tym oknie wysyła
zmianę na Allegro.

### E5. Czego ma NIE być

- Ordlak nie proponuje anulowania zamówienia ani cofnięcia statusu —
  to nie jest na liście dozwolonych działań.
- Nie proponuje też niczego „przy okazji", o co nie prosiłeś.
- Jeśli nie jest pewny, którego zamówienia dotyczy prośba, ma **dopytać**,
  a nie zgadywać.

---

## Gdyby coś poszło nie tak

Logi backendu na żywo:

```bash
journalctl -u ordly -f
```

**Przycisk odpowiada błędem 404** — backend jest stary. Wróć do części B,
kroki B4–B6.

**Przycisk odpowiada błędem 422** — Pi odrzuciło parametry (np. Ordlak
podał numer oferty, której nie ma). To działa zgodnie z projektem: zapis
jest walidowany po stronie Pi, a nie przyjmowany na słowo. Poproś Ordlaka
jeszcze raz, wskazując ofertę nazwą.

**Telefon pokazuje stary wygląd** — patrz C5. Najczęstsza przyczyna to
PWA trzymająca starą wersję w pamięci, a nie nieudane wdrożenie.

Powrót do stanu sprzed aktualizacji — **kolejność ma znaczenie**, jedna
komenda na raz:

```bash
sudo systemctl stop ordly
```

```bash
cd ~/ordly/backend
```

```bash
cp ~/ordly-przed-nokturn-2026-09-21.db data/ordly.db
```

```bash
git checkout HEAD~1
```

```bash
uv sync
```

```bash
sudo systemctl start ordly
```

Po takim cofnięciu napisz do mnie — trzeba będzie jeszcze przywrócić
poprzednią paczkę PWA i poprzedni `.exe`, a na Pi wrócić z „odłączonego"
stanu gita (`git checkout main`).
