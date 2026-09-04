# ORDLY — wdrożenie zmian z 26 sierpnia 2026

Ta paczka to sześć rzeczy naraz:

1. **Dyskusje** — wiadomości były ułożone od najnowszej i pokazywały surowe
   `<br>` oraz `<strong>` jako tekst.
2. **Poczta** — zamiast treści maila widać było jego kod źródłowy
   (`<!DOCTYPE HTML ...`), a jedynym wyjściem był link „Otwórz w Gmailu”.
3. **Allegro Lokalnie** — nowy kanał, w PEŁNEJ integracji: sprzedaż z tego
   serwisu staje się normalnym zamówieniem (Zamówienia, przychód, lista „do
   spakowania", odjęcie stanów magazynowych), a wiadomości i zmiany statusu
   trafiają na telefon jako push. Wymaga jednorazowego powiązania ofert
   z magazynem — patrz CZĘŚĆ E.
4. **Dyskusje z Allegro.pl** — mail „kupujący rozpoczął z Tobą dyskusję”
   od teraz wywołuje push, razem z terminem odpowiedzi, którego API Allegro
   w ogóle nie zwraca.
5. **Powiadomienia push** — koniec z `<b>` na ekranie blokady, wszystkie
   treści skrócone do „ile, czego, za ile”.
6. **Produkty główne i podprodukty** — butelka sprzedaje się razem
   z nakrętką i kroplomierzem, więc ich stany schodzą teraz same, bez
   wpisywania trzech składników do każdej receptury. Patrz CZĘŚĆ F.

> **Kolejność ma znaczenie.** CZĘŚĆ A (GitHub) → CZĘŚĆ B (Pi) →
> CZĘŚĆ C (telefon) → CZĘŚĆ D (komputer) → CZĘŚĆ E (powiązanie ofert
> Allegro Lokalnie) → CZĘŚĆ F (podprodukty). Aplikacje pytają backend o rzeczy, których stara wersja
> na Pi jeszcze nie zna — bez aktualizacji Pi ekran Poczty pokaże błąd 404.

---

## CZĘŚĆ A — wypchnięcie na GitHub (na komputerze)

### A1. Wejdź do repozytorium

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

### A2. Zobacz, co pójdzie w commicie

```bash
git status --short
```

Katalog `features_folder/` to Twoje notatki ze zgłoszeniami — jeśli nie chcesz
ich w repo, dopisz go do `.gitignore` przed następnym krokiem.

### A3. Dodaj zmiany

```bash
git add backend desktop mobile docs
```

### A4. Zrób commit

```bash
git commit -m "Produkty glowne i podprodukty w magazynie"
```

Jeśli `git status --short` w kroku A2 nic nie pokazał, poprzednia paczka
jest już zacommitowana — pomiń A3 i A4, idź od razu do A5.

### A5. Wypchnij na GitHub

```bash
git push origin main
```

Jeśli `git push` poprosi o dane logowania, a masz włączone 2FA na GitHubie —
hasło do konta nie zadziała. Potrzebny jest **personal access token**
(GitHub → Settings → Developer settings → Personal access tokens) wklejony
w miejsce hasła.

---

## CZĘŚĆ B — Raspberry Pi (przez SSH)

### B1. Połącz się z Pi

```bash
ssh cewastack2@cewastack2
```

### B2. Wejdź do katalogu backendu

```bash
cd ~/ordly/backend
```

### B3. Sprawdź, czy nie ma lokalnych zmian blokujących pobranie

```bash
git status --short
```

Jeśli pokaże zmodyfikowane pliki (linie z `M`), cofnij je — inaczej `git pull`
odmówi. **Nie cofa to `.env`**, bo ten plik nie jest w repozytorium:

```bash
git restore .
```

### B4. Pobierz nową wersję

```bash
git pull
```

### B5. Zainstaluj zależności

```bash
uv sync
```

### B6. POPRAW `MAIL_WATCH_SENDERS` — to najważniejszy krok w całej instrukcji

Sprawdź aktualną wartość:

```bash
grep MAIL_WATCH_SENDERS ~/ordly/backend/.env
```

Jeśli widzisz `allegro.pl,olx.pl` (tak było w instrukcji z 4 sierpnia), to
**ORDLY nie pobiera żadnych maili z Allegro ani z Allegro Lokalnie**. IMAP
dopasowuje nagłówek `From` po **podciągu**, a `allegro.pl` nie występuje ani
w `noreply@allegromail.pl`, ani w `powiadomienia@allegrolokalnie.pl` — po
„allegro” idzie tam „mail.pl” albo „lokalnie.pl”.

Otwórz plik:

```bash
nano ~/ordly/backend/.env
```

Ustaw dokładnie tak (krótkie tokeny, nie domeny):

```
MAIL_WATCH_SENDERS=allegro,olx
```

Zapisz i wyjdź: `Ctrl+O`, `Enter`, `Ctrl+X`.

### B7. Wykonaj migrację bazy

Ta paczka niesie DWIE migracje: `0008` (rozdzielenie kanału Allegro
Lokalnie od Allegro.pl) i `0009` (kolumna produktu głównego
w magazynie). Polecenie poniżej wykonuje obie za jednym razem.

Migracja `0008` nie zmienia struktury tabel — poprawia **dane**: maile
z Allegro Lokalnie zapisane wcześniej pod etykietą „Allegro” dostają własny
kanał. Jest odwracalna (`alembic downgrade 0007`).

```bash
uv run alembic upgrade head
```

Ma wypisać `Running upgrade 0007 -> 0008, split allegro_lokalnie mail source`.

### B8. Zrestartuj usługę

```bash
sudo systemctl restart ordly
```

### B9. Sprawdź, czy wstała

```bash
sudo systemctl status ordly --no-pager
```

Szukasz `Active: active (running)`. Jeśli `failed`:

```bash
journalctl -u ordly -n 50 --no-pager
```

### B10. Weź token do dalszych sprawdzeń

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
```

Skopiuj wartość `token` — w kolejnych krokach wklejasz ją zamiast `TU_TOKEN`.

### B11. Sprawdź, że skrzynka obserwuje właściwych nadawców

```bash
curl -s http://localhost:8000/api/v1/mail/status -H "Authorization: Bearer TU_TOKEN"
```

W odpowiedzi `"watch_senders":["allegro","olx"]` — jeśli nadal widzisz
`allegro.pl`, usługa nie przeczytała nowego `.env`. Wróć do B6 i B8.

### B12. Wymuś pobranie maili

```bash
curl -s -X POST http://localhost:8000/api/v1/mail/sync -H "Authorization: Bearer TU_TOKEN"
```

- `{"new_count":7,"configured":true}` — działa.
- `{"new_count":0,"configured":true}` — połączenie OK, ale w skrzynce nie ma
  nic od obserwowanych nadawców z ostatnich 7 dni.
- Błąd 502 „Logowanie IMAP odrzucone…” — złe `IMAP_USER`/`IMAP_PASS`
  (najczęściej zwykłe hasło zamiast hasła aplikacji Google).

### B13. Sprawdź NOWY endpoint treści maila

Message-ID zawiera `<`, `>` i `@`, więc w adresie musi być zakodowany —
to polecenie bierze pierwszy mail z listy i robi to za Ciebie (wklej swój
token w OBU miejscach):

```bash
MSG=$(curl -s "http://localhost:8000/api/v1/mail/messages?limit=1" -H "Authorization: Bearer TU_TOKEN" | python3 -c "import sys,json,urllib.parse; print(urllib.parse.quote(json.load(sys.stdin)[0]['message_id'], safe=''))")
```

```bash
curl -s "http://localhost:8000/api/v1/mail/messages/$MSG/body" -H "Authorization: Bearer TU_TOKEN" | head -c 300
```

Ma wrócić JSON z polami `html_body` i `plain_body`. Jeśli widzisz 404
z treścią „Wiadomości … nie ma już w skrzynce” — mail został skasowany
w Gmailu; weź inny. Jeśli 502 — problem z logowaniem IMAP (patrz B12).

Zakończ sesję SSH:

```bash
exit
```

---

## CZĘŚĆ C — telefon (PWA)

> **Sam `git pull` na Pi NIE aktualizuje aplikacji na telefonie.** Backend
> serwuje ją jako zbudowaną, statyczną paczkę z osobnego katalogu. Ten krok
> jest łatwo pominąć — bez niego telefon pokaże starą wersję, mimo że backend
> jest już nowy.

### C1. Zbuduj aplikację mobilną (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom\mobile
```

```bash
npx expo export -p web
```

Trwa 1–2 minuty. Efekt trafia do `mobile\dist\`.

### C2. Spakuj i wyślij na Pi

Uruchom to z katalogu `mobile`. `tar` jest wbudowany w Windows 11 i działa
tak samo w PowerShellu, jak w Git Bashu — **nie używaj tu `Compress-Archive`
ze zmienną `$env:USERPROFILE`**: w bashu ta zmienna nie istnieje, archiwum
trafia w bezsensowną ścieżkę, `scp` nie ma czego wysłać, a krok C3 i tak
zdąży wyczyścić katalog na Pi. Efektem jest pusty `webapp_dist`
i biały ekran na telefonie.

```bash
tar -czf mobile-dist.tgz -C dist .
```

```bash
scp mobile-dist.tgz cewastack2@cewastack2:~/
```

Zanim pójdziesz dalej, upewnij się, że plik faktycznie doleciał:

```bash
ssh cewastack2@cewastack2 "ls -lh ~/mobile-dist.tgz"
```

Ma pokazać kilka megabajtów. Jeśli pokaże `No such file` — **zatrzymaj się
tutaj**, nie wykonuj C3, bo skasujesz działającą aplikację.

### C3. Podmień paczkę na Pi

Najpierw sprawdź, gdzie backend NAPRAWDĘ szuka tych plików — to nie jest
`~/ordly/mobile/dist`:

```bash
ssh cewastack2@cewastack2 "grep WEB_APP_DIST_PATH ~/ordly/backend/.env"
```

Odpowiedź to `WEB_APP_DIST_PATH=/home/cewastack2/ordly/webapp_dist`. Podmień
zawartość TEGO katalogu:

```bash
ssh cewastack2@cewastack2 "rm -rf ~/ordly/webapp_dist/* && tar -xzf ~/mobile-dist.tgz -C ~/ordly/webapp_dist && chmod -R a+rX ~/ordly/webapp_dist && rm ~/mobile-dist.tgz && sudo systemctl restart ordly"
```

### C4. Sprawdź, że Pi serwuje świeżą wersję

Nie wystarczy sprawdzić `index.html` — biały ekran bierze się stąd, że
strona się ładuje, a **bundle JS pod nią nie**. Sprawdź oba:

```bash
ssh cewastack2@cewastack2 "cd ~/ordly/webapp_dist && ls && curl -s -o /dev/null -w 'index.html: %{http_code}\n' http://localhost:8000/ && curl -s -o /dev/null -w 'bundle: %{http_code}\n' http://localhost:8000/_expo/static/js/web/\$(grep -o 'AppEntry-[a-z0-9]*\.js' index.html)"
```

Ma wypisać listę plików (`_expo`, `assets`, `index.html`, `sw.js`, …)
oraz **`index.html: 200`** i **`bundle: 200`**.

- Pusta lista plików → C2/C3 nie doszło do skutku, powtórz od C2.
- `bundle: 404` → w `webapp_dist` jest niepełna paczka, powtórz od C2.
- **`bundle: 401`** → brak praw odczytu, nie problem z tokenem. Starlette
  zamienia `PermissionError` na 401 (dosłownie, w swoim `staticfiles.py`),
  więc telefon dostaje `index.html`, ale nie dostaje kodu aplikacji i widzi
  biały ekran. Naprawa:

```bash
ssh cewastack2@cewastack2 "chmod -R a+rX ~/ordly/webapp_dist"
```

> **Dlaczego `a+rX`, a nie `u+rX`:** `u+rX` daje odczyt tylko właścicielowi
> katalogu. Wystarczy, że usługa ORDLY chodzi jako inny użytkownik albo
> rozpakowanie ustawi katalogowi tryb bez `x`, i cały podkatalog `_expo/`
> staje się dla niej niewidoczny. Wielkie `X` (nie `x`) nadaje prawo wejścia
> tylko katalogom, nie robi z plików JS programów wykonywalnych.

### C5. Odśwież aplikację na telefonie

**Zamknij ORDLY całkowicie** (przesuń w górę w przełączniku aplikacji)
i otwórz ponownie. Service worker podmienia się dopiero przy następnym
uruchomieniu — zwykłe odświeżenie zostawia starą wersję.

### C6. Sprawdź, co miało się naprawić

- **Poczta → dowolny mail z Allegro** — ma się wyświetlić treść (nagłówek
  Allegro, akapity, przycisk), a nie `<!DOCTYPE HTML ...`. Obrazki z sieci są
  zablokowane celowo (to zwykle piksele śledzące) — pod treścią jest o tym
  jedno zdanie i link do Gmaila.
- **Poczta → filtr „Allegro Lokalnie”** — powinien się pojawić obok Allegro
  i OLX. Maile z tego serwisu mają etykietę „AL” i notkę „nie ma API —
  zamówieniem zarządzasz na stronie serwisu”.
- **Dyskusje → dowolny wątek** — najstarsza wiadomość u góry, najnowsza na
  dole, widok otwiera się przewinięty do najnowszej. Żadnych `<br>` w treści.
- **Ustawienia → Powiadomienia push → Wyślij testowe powiadomienie** — ma
  przyjść krótkie powiadomienie bez znaczników HTML.

---

## CZĘŚĆ D — komputer (aplikacja desktopowa)

### D1. Wejdź do katalogu aplikacji

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

### D2. Zainstaluj zależności (nowych nie ma, ale to nic nie kosztuje)

```bash
npm install
```

### D3. Zbuduj plik .exe

```bash
npm run dist
```

Efekt w `desktop\release\` — `ORDLY-Setup-0.1.0.exe` (instalator) albo
`ORDLY-0.1.0-portable.exe` (bez instalacji).

Jeśli zobaczysz `EBUSY: resource busy or locked` — masz uruchomioną starą
wersję ORDLY albo otwarty Eksplorator w `release\win-unpacked`:

```bash
taskkill /IM ORDLY.exe /F
```

```bash
rmdir /s /q release\win-unpacked
```

### D4. Zainstaluj i sprawdź

Po instalacji zaloguj się jak dotąd (adres
`https://cewastack2.tail7f5a20.ts.net`, login `admin`).

- **Dyskusje** — kolejność wiadomości i formatowanie jak na telefonie; linki
  w treści otwierają się w przeglądarce systemowej.
- **Poczta** — treść maila w ramce, filtr „Allegro Lokalnie”, link do Gmaila
  jako opcja dodatkowa, nie jedyna.

---

## CZĘŚĆ E — Allegro Lokalnie: powiąż oferty z magazynem

**Ten krok jest obowiązkowy, jeśli stany magazynowe mają się zgadzać.**

Sprzedaż z Allegro Lokalnie jest teraz pełnoprawnym zamówieniem: trafia do
zakładki Zamówienia, liczy się do przychodu, wchodzi na listę „do spakowania"
i **odejmuje stany magazynowe**. Ostatnie działa jednak dopiero wtedy, gdy
ORDLY wie, z czego składa się dane ogłoszenie.

### Skąd bierze się identyfikator oferty

Allegro Lokalnie nie podaje w mailu numeru ogłoszenia — jest tylko tytuł.
ORDLY wylicza więc z tytułu stały skrót w postaci `al:xxxxxxxxxxxx`. Jest ten
sam przy każdej kolejnej sprzedaży tego ogłoszenia, więc powiązanie ustawiasz
raz.

> **Uwaga, której nie da się obejść bez API:** zmiana tytułu ogłoszenia na
> Allegro Lokalnie tworzy NOWY identyfikator i powiązanie trzeba ustawić
> ponownie. Dowiesz się o tym od razu — przy pierwszej sprzedaży po zmianie
> przyjdzie powiadomienie „Sprzedaż poza magazynem", a nie ciche rozjechanie
> się stanów.

### E1. Poczekaj na pierwszą sprzedaż (albo wymuś synchronizację skrzynki)

Po pierwszej sprzedaży oferta sama zgłosi się jako niepowiązana. Zobaczysz
wtedy powiadomienie **„Sprzedaż poza magazynem"** — to jest sygnał do
wykonania kroku E2, a nie awaria.

### E2. Powiąż ofertę ze składnikami

W aplikacji desktopowej: **Magazyn → Powiązania ofert**. Oferta czeka na
liście niepowiązanych, z tytułem i identyfikatorem `al:…`. Wskaż, z czego się
składa i w jakiej ilości.

Przykład: ogłoszenie „100szt. Butelka Gorilla 10ml" to sto butelek w jednej
paczce, więc składnik to `BUT-GOR-10` w ilości **100**. Przy sprzedaży
4 sztuk tej oferty ORDLY zdejmie 400 butelek.

Alternatywnie z Telegrama:

```
/stock link al:21c81ecdcc65 BUT-GOR-10 100
```

### E3. Nadrób stany sprzed powiązania (opcjonalnie)

Jeśli oferta sprzedała się już zanim ją powiązałeś, w „Powiązaniach ofert"
jest **korekta wsteczna** — zdejmie sztuki z tych zamówień, które wcześniej
nie ruszyły magazynu. Bez tego stany będą zawyżone o tamtą sprzedaż.

### Co się NIE dzieje przy Allegro Lokalnie

- **Nie ma zmiany statusu na serwisie.** „Oznacz jako spakowane/wysłane"
  działa lokalnie w ORDLY, ale nie wysyła niczego do Allegro Lokalnie — ten
  serwis nie ma API. Wysyłkę potwierdzasz na jego stronie.
- **Nie ma anulowania ani zwrotów.** Mail o anulowaniu nie tworzy dziś korekty
  stanów; gdyby taka sytuacja wystąpiła, stan trzeba poprawić ręcznie
  w Magazynie. Nie mam próbki takiego maila, więc nie zgaduję jego formatu.

---

## CZĘŚĆ F — produkty główne i podprodukty

Do tej pory, żeby sprzedaż butelki zdejmowała też nakrętkę i kroplomierz,
trzeba było wpisać wszystkie trzy do receptury KAŻDEJ oferty osobno.
Od teraz relacja jest własnością samego produktu: ustawiasz ją raz,
a działa przy każdej ofercie i w każdym serwisie.

---

### F0. Skrót: masz już wdrożone A–E

Ta zmiana dotyka tylko backendu i aplikacji na komputerze. Poniżej pełna
lista kroków — **CZĘŚĆ C (telefon) odpada w całości**, bo aplikacja
mobilna nie zmieniła się ani o linijkę.

**Kolejność jest ważna: najpierw Pi, potem komputer.** Nowy ekran Magazynu
korzysta z endpointów, których stary backend nie zna.

#### 1. Komputer — wypchnij zmiany

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

```bash
git add backend desktop docs
```

```bash
git commit -m "Produkty glowne i podprodukty w magazynie"
```

```bash
git push origin main
```

#### 2. Pi — pobierz i zmigruj

```bash
ssh cewastack2@cewastack2
```

```bash
cd ~/ordly/backend
```

```bash
git pull
```

```bash
uv run alembic upgrade head
```

Ma wypisać dokładnie jedną linię:
`Running upgrade 0008 -> 0009, add parent_item_id to inventory_items`.

Jeśli wypisze też `0007 -> 0008` — poprzednia paczka nie była wdrożona
i właśnie się dołożyła. Nic złego, obie migracje są bezpieczne.

**`uv sync` nie jest potrzebne** — ta zmiana nie dokłada żadnej biblioteki.

```bash
sudo systemctl restart ordly
```

```bash
sudo systemctl status ordly --no-pager
```

Szukasz `Active: active (running)`.

#### 3. Pi — sprawdź, że nowe endpointy odpowiadają

Weź token (jak w kroku B10):

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
```

```bash
TOKEN=TU_TOKEN
```

Lista magazynowa ma teraz nieść pole `parent_sku` przy każdym produkcie:

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/stock | python3 -m json.tool | grep -m3 parent_sku
```

Jeśli `grep` nic nie zwróci, backend nadal chodzi na starym kodzie —
wróć do kroku 2.

```bash
exit
```

#### 4. Komputer — przebuduj aplikację

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm run dist
```

Zainstaluj `desktop\release\ORDLY-Setup-0.1.0.exe`. Jeśli wyskoczy
`EBUSY: resource busy or locked`, zamknij działającą aplikację:

```bash
taskkill /IM ORDLY.exe /F
```

#### 5. Sprawdź w aplikacji

Otwórz **Magazyn → Produkty**. Lista ma wyglądać jak dotąd — każdy
produkt osobno, bo żadnej relacji jeszcze nie ma. Przy każdym wierszu
pojawił się nowy przycisk **Podprodukty**. Od tego momentu idź do F1.

> Gdyby lista magazynowa była pusta, a wcześniej nie była: to znak, że
> aplikacja rozmawia ze starym backendem. Wróć do kroku 2.

---

### Zasady, które warto znać zanim zaczniesz

- **Proporcja zawsze 1:1.** Sto butelek to sto nakrętek. Nie ma pola
  „ile sztuk na jedną" i nie będzie — dla zestawów typu „2 butelki
  w komplecie" nadal służy ilość w recepturze oferty.
- **Ręczna korekta NIE kaskaduje.** `/stock add BUT10 50`, stepper
  w Magazynie i inwentaryzacja zmieniają stan tylko tego jednego SKU.
  To celowe: nakrętki przyjeżdżają osobnym kartonem i liczy się je
  osobno. Kaskada dotyczy wyłącznie sprzedaży, anulowania i zwrotu.
- **Jeden poziom zagnieżdżenia.** Podprodukt nie może mieć własnych
  podproduktów. Próba kończy się czytelnym błędem, nie zapisem.
- **Podprodukty znikają z listy magazynowej**, ale zostają na liście
  zakupów — kończące się nakrętki nadal Cię o sobie przypomną.

### F1. Ustaw relację (raz na trójkę produktów)

W aplikacji desktopowej: **Magazyn → Produkty**, wiersz produktu
głównego → przycisk **Podprodukty** → wybierz produkt z listy → **Dodaj**.
Ten sam modal służy do odłączania.

Albo z Telegrama:

```bash
/stock parent NAK10 BUT10
```

Myślnik odłącza:

```bash
/stock parent NAK10 -
```

### F2. Uprość istniejące receptury (opcjonalnie, ale warto)

Jeżeli masz już receptury wypisane po staremu — butelka, nakrętka
i kroplomierz jako trzy składniki jednej oferty — **nic się nie psuje**:
ORDLY wykrywa, że nakrętka jest już w recepturze, i nie odejmuje jej
drugi raz przez kaskadę. Możesz jednak zostawić w recepturze sam produkt
główny (Magazyn → Powiązania ofert → edycja) i mieć o dwie pozycje mniej
do pilnowania przy każdej nowej ofercie.

Stary, wieloskładnikowy sposób zostaje na stałe — jest potrzebny do
prawdziwych zestawów, łączących niezależne produkty główne.

### F3. Sprawdź, że działa

Po pierwszej sprzedaży powiązanej oferty otwórz historię (ikona zegara
w Magazynie) dla nakrętki. Powinien tam być wpis z tym samym numerem
zamówienia co przy butelce i dopiskiem „(podprodukt: BUT10)".

Z linii poleceń na Pi:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/stock/BUT10/sub-items" | python3 -m json.tool
```

### Czego ta zmiana NIE robi

- **Nie rusza aplikacji na telefonie.** Mobilny Magazyn to podgląd,
  więc pokazuje nadal płaską listę — nakrętka i kroplomierz są tam
  osobnymi pozycjami. Hierarchię widać w aplikacji na komputerze.
- **Nie kaskaduje przy korekcie wstecznej** („Powiązania ofert →
  korekta wsteczna"). Ta funkcja odejmuje sprzedaż sprzed powstania
  receptury i rusza wyłącznie składniki wypisane w recepturze.

---

## Dyskusje z Allegro.pl — powiadomienie o rozpoczęciu

Do tej pory o nowej dyskusji dowiadywałeś się dopiero wtedy, gdy sam
otworzyłeś ekran Dyskusji — ORDLY odpytuje `/sale/issues` w Allegro
wyłącznie na żądanie, nie w tle. Od teraz mail od `powiadomienia@allegro.pl`
o rozpoczętej dyskusji wywołuje push:

> **Nowa dyskusja**
> Rexpiot: niezgodny z opisem — odpowiedz do 29.07, 08:41

Kliknięcie otwiera wątek pod `/issues/<id>`.

**Termin odpowiedzi jest tylko w mailu.** Allegro pisze w nim „jeśli nie
wypowiesz się do DD.MM.RRRR GG:MM, włączymy się do rozmowy” — API tej daty
nie udostępnia w żaden sposób. To jedyny powód, dla którego czytamy tu
pocztę mimo istnienia API.

### Czego ta zmiana świadomie NIE robi

- **Nie powiadamia o zwrotach z maila.** Zwroty pobiera synchronizacja
  z API (`/order/customer-returns`) i to ona wysyła powiadomienie. Drugi tor
  ze skrzynki dałby dwa powiadomienia o jednym zwrocie. Mail o odstąpieniu
  od umowy nadal widać w zakładce Poczta — po prostu nie dzwoni drugi raz.
- **Nie powiadamia o zamówieniach z maila.** Z tego samego powodu.
- **Nie tworzy zamówień z poczty Allegro.pl.** Zamówienia z Allegro.pl
  przychodzą wyłącznie z API. Z poczty powstają tylko zamówienia z Allegro
  Lokalnie, bo tamten serwis API nie ma.

### Warunek działania

Ta funkcja korzysta z tej samej skrzynki co reszta — jeśli w kroku **B6**
`MAIL_WATCH_SENDERS` nie zawiera `allegro`, maile o dyskusjach w ogóle nie
wpadną do bazy i push nie przyjdzie.

### Jak sprawdzić po wdrożeniu

Nie da się tego wywołać sztucznie (musiałby przyjść prawdziwy mail).
Sprawdzasz przy najbliższej dyskusji — albo wcześniej, patrząc czy backend
w ogóle widzi maile z Allegro:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/mail/messages?source=allegro&limit=5" | python3 -m json.tool
```

---

## Powiadomienia push — co się zmieniło

Pełny podgląd wszystkich treści: `backend/docs/podglad-powiadomien-push.html`
(otwórz w przeglądarce). Odświeżasz go poleceniem:

```bash
cd C:\Users\kukil\Desktop\Projects\toom\backend
```

```bash
.venv\Scripts\python.exe scripts\generate_push_preview.py
```

Zasady wpisane w kod:

- **Treść mówi ile, czego i za ile.** Login kupującego, pełny numer
  zamówienia, numer zwrotu i szczegóły dyskusji zostają w aplikacji.
- **Katalog nie ma pozycji-widm.** Wpis `unanswered_question` nie miał
  w kodzie ani jednego nadawcy — nic nigdy go nie wysyłało. Zastąpił go
  `new_dispute`, który wysyła skrzynka (patrz sekcja wyżej).
- **Treść formatuje kanał, nie zdarzenie.** Telegram dostaje pogrubienia
  i `<code>` z komendą do skopiowania; push dostaje czysty tekst.
  Wspólna ścieżka `send_text` przepuszcza treść przez `strip_html`, więc
  nawet przyszły tekst pisany pod Telegram nie wypłynie na telefon z `<b>`.
- **Ikona jest jedna** — ta sama co ikona aplikacji. Ikony per typ zdarzenia
  zostały odrzucone: iOS przy Web Push z PWA i tak pokazuje ikonę aplikacji.

---

## Gdyby coś nie zagrało

### Poczta pokazuje 404 albo „stara wersja backendu”

Pi nie ma jeszcze nowej wersji — wróć do CZĘŚCI B, kroki B4–B8.

### Skrzynka pusta mimo poprawnego hasła

Najpewniej `MAIL_WATCH_SENDERS`. Krok B6 i B11 — wartość musi brzmieć
`allegro,olx`, nie `allegro.pl,olx.pl`.

### Mail otwiera się, ale zamiast treści widać ostrzeżenie

Treść maila jest dociągana ze skrzynki dopiero przy otwarciu (w bazie leżą
tylko metadane i krótki podgląd — pełne maile z obrazkami zajęłyby na Pi
kilka megabajtów każdy i mnożyłyby się w kopiach zapasowych). Ostrzeżenie
znaczy, że IMAP nie odpowiedział albo mail zniknął ze skrzynki. Sprawdź
`sudo systemctl status ordly` i krok B12.

### Telefon dalej pokazuje starą wersję

CZĘŚĆ C, krok C3 — sprawdź `WEB_APP_DIST_PATH` i podmień zawartość TEGO
katalogu, nie `~/ordly/mobile/dist`. Potem C5: zamknij aplikację całkowicie.

### Chcę cofnąć migrację bazy

```bash
ssh cewastack2@cewastack2 "cd ~/ordly/backend && uv run alembic downgrade 0007"
```

Maile z Allegro Lokalnie wracają wtedy pod etykietę „Allegro” — czyli do
stanu sprzed wdrożenia. Nic nie ginie.
