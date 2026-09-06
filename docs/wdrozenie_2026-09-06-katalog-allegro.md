# ORDLY — 6 września 2026: magazyn pobiera asortyment z Allegro

**Objaw:** magazyn nie odejmował stanów, a komunikat o braku powiązania
wisiał w kółko, bo nie dało się wskazać, do której oferty podpięty jest
produkt.

**Przyczyna.** Sam mechanizm odejmowania był sprawny. Odpalał się jednak
tylko dla ofert, które ORDLY potrafi rozłożyć na produkty magazynowe —
przez recepturę albo przez SKU równe numerowi oferty. A jedynym źródłem
numerów ofert w całym systemie była **historia sprzedaży**. Stąd błędne
koło: żeby powiązać ofertę, musiała się najpierw sprzedać — a ta
sprzedaż z definicji przechodziła obok magazynu.

Do tego metoda pobierająca oferty z Allegro istniała w kodzie, ale
**nikt jej nigdy nie wołał**, i w dodatku brała tylko pierwsze 100 ofert.

**Naprawa.** Magazyn pobiera teraz asortyment prosto z Allegro
(`GET /sale/offers`, ze stronicowaniem) do nowej tabeli
`marketplace_offers`. Oferta jest znana, **zanim cokolwiek się sprzeda**,
więc powiązanie wskazuje realnie istniejącą ofertę, a nie numer
przepisany z ręki.

W aplikacji desktopowej doszła trzecia zakładka w Magazynie:
**Asortyment Allegro**.

> **Uwaga — trzy rzeczy do zrobienia, nie jedna:**
> migracja bazy (`0011`), restart usługi **oraz przebudowanie aplikacji
> desktopowej** (`.exe`). Sama aktualizacja Pi nie doda zakładki.
> `.env` bez zmian, nowych zależności Pythona nie ma.

---

## Zanim zaczniesz: jedno uprawnienie po stronie Allegro

Pobieranie ofert wymaga uprawnienia **do odczytu ofert** na poziomie
**rejestracji aplikacji** w `apps.developer.allegro.pl`. To ta sama
pułapka, co kiedyś przy Dyskusjach (403 `AccessDenied`) — sam kod ani
ponowne logowanie tego nie naprawią, jeśli aplikacja nie ma uprawnienia
przyznanego w portalu.

**Nie zgaduj, czy je masz.** Krok **B7** poniżej sprawdza to jednym
poleceniem. Jeśli wyjdzie 403 — instrukcja naprawy jest w **CZĘŚCI D**.

---

## CZĘŚĆ A — na komputerze

### A1. Wejdź do repozytorium

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

### A2. Commit i push

```bash
git add backend desktop docs
```

```bash
git commit -m "Magazyn pobiera asortyment z Allegro i wiaze go z ofertami"
```

```bash
git push origin main
```

### A3. Przebuduj aplikację desktopową

To trwa kilka minut. Buduje `.exe` z nową zakładką.

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm run dist
```

Gotowy instalator wyląduje w `desktop\release\ORDLY-Setup-0.1.0.exe`.
Zainstaluj go **dopiero po** wykonaniu CZĘŚCI B — nowa zakładka bez
zaktualizowanego backendu pokaże pusty katalog i błąd przy pobieraniu.

---

## CZĘŚĆ B — Raspberry Pi (przez SSH)

### B1. Połącz się i wejdź do backendu

```bash
ssh cewastack2@cewastack2
```

```bash
cd ~/ordly/backend
```

### B2. Zrób kopię bazy przed migracją

Migracja tylko **dodaje** nową tabelę i niczego nie kasuje, ale kopia
kosztuje sekundę:

```bash
cp -v data/ordly.db "backups/ordly_przed_katalogiem_$(date +%F).db"
```

> Nie używaj `scripts/backup_db.sh` — ten skrypt szuka pliku
> `data/toom.db` ze starej nazwy projektu i wywali się błędem
> „Nie znaleziono bazy danych".

### B3. Sprawdź, czy nic nie blokuje pobrania

```bash
git status --short
```

Jeśli pokaże zmodyfikowane pliki (linie z `M`), cofnij je — inaczej
`git pull` odmówi. **Nie cofa to `.env`**, bo tego pliku nie ma
w repozytorium:

```bash
git restore .
```

### B4. Pobierz nową wersję

```bash
git pull
```

### B5. Zrób migrację bazy

Tworzy tabelę `marketplace_offers` na katalog ofert. **Bez tego kroku
pobieranie asortymentu wywali się przy pierwszej próbie.**

```bash
uv run alembic upgrade head
```

Ostatnia linia ma brzmieć `Running upgrade 0010 -> 0011, create
marketplace_offers`.

### B6. Zrestartuj usługę i sprawdź, czy wstała

```bash
sudo systemctl restart ordly
```

```bash
sudo systemctl status ordly --no-pager
```

Gdyby coś było nie tak:

```bash
journalctl -u ordly -n 50 --no-pager
```

### B7. Sprawdź uprawnienie do ofert — najważniejszy krok

Najpierw token — odpowiedź ma postać `{"token":"..."}`, skopiuj wartość
z cudzysłowu:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
```

Teraz pobierz asortyment (wklej token zamiast `TU_TOKEN`):

```bash
curl -s -X POST http://localhost:8000/api/v1/stock/catalog/sync -H "Authorization: Bearer TU_TOKEN"
```

**Co ma wyjść:**

```
{"marketplace":"allegro","fetched":37,"auto_linked":0,"unlinked":37,...}
```

Liczba przy `fetched` to Twoje oferty na Allegro. Jeśli się zgadza —
działa, przejdź do CZĘŚCI C.

**Jeśli zamiast tego widzisz `503` albo tekst z `AccessDenied` / `403`** —
brakuje uprawnienia. Idź do CZĘŚCI D.

---

## CZĘŚĆ C — pierwsze uruchomienie w aplikacji

Zainstaluj nowy `.exe` z kroku A3 i otwórz ORDLY.

### C1. Pobierz asortyment

**Magazyn → Asortyment Allegro → „Pobierz z Allegro"**.

Zobaczysz listę swoich ofert ze zdjęciem, ceną i stanem z Allegro. Każda
ma etykietę mówiącą, czy jej sprzedaż rusza magazyn:

| Etykieta | Znaczenie |
|---|---|
| **zdejmuje stan** (zielona) | działa — sprzedaż odejmie towar |
| **sygnatura pasuje — dowiąż** (żółta) | jeszcze **nie działa**, jedno kliknięcie od działania |
| **nie rusza magazynu** (szara) | sprzedaż przechodzi obok magazynu |

### C2. Załóż brakujące produkty

Kliknij **„Zaznacz wszystkie bez powiązania"**, potem **„Załóż
w magazynie i powiąż"**. ORDLY utworzy produkty magazynowe z nazw i
stanów z Allegro i od razu je powiąże.

> Stan początkowy bierze się z liczby sztuk wystawionych w ofercie. Jeśli
> kilka ofert sprzedaje ten sam fizyczny towar, ta liczba będzie
> **zawyżona** — popraw ją ręczną korektą w zakładce Produkty.

### C3. Rozpisz zestawy

Oferta typu „butelka + kroplomierz + nakrętka" to jeden produkt tylko
z pozoru. Kliknij przy niej **„Edytuj składniki"** i dopisz wszystkie
trzy pozycje — dopiero wtedy sprzedaż zdejmie każdą z nich.

### C4. Nadrób sprzedaż sprzed powiązania

**Magazyn → Powiązania ofert →** przy każdej ofercie **„Uzupełnij
wstecz"**. Pokaże podgląd: które zamówienia i ile sztuk. Rozliczenie idzie
per zamówienie, więc **powtórzenie nie odejmie tego samego dwa razy**.

### C5. Sprawdź, że komunikat zniknął

Wróć na **Asortyment Allegro** i wybierz filtr **„Bez powiązania"**.
Lista ma być pusta. Czerwony licznik przy zakładce *Powiązania ofert*
i baner na telefonie znikną same.

---

## CZĘŚĆ D — jeśli w B7 wyszło 403 / AccessDenied

### D1. Włącz uprawnienie w portalu Allegro

Wejdź na `https://apps.developer.allegro.pl`, otwórz swoją zarejestrowaną
aplikację i zaznacz uprawnienie **do odczytu ofert** (sekcja dotycząca
ofert / sprzedaży). Zapisz.

### D2. Pobierz świeży token przez tunel SSH

Na komputerze, w **nowym** oknie:

```bash
ssh -L 53682:localhost:53682 cewastack2@cewastack2
```

W tej samej sesji:

```bash
cd ~/ordly/backend && uv run python scripts/allegro_login.py
```

Skrypt wypisze URL — otwórz go w przeglądarce i zatwierdź dostęp. Świeże
tokeny zapiszą się w bazie.

> Samo ponowne logowanie **nie doda** uprawnienia, którego aplikacja nie
> ma przyznanego w portalu. Krok D1 musi być pierwszy.

### D3. Zrestartuj i powtórz test

```bash
sudo systemctl restart ordly
```

Powtórz **B7**.

---

## Jak działa automatyczne wiązanie (i dlaczego tak)

ORDLY dowiązuje ofertę do produktu magazynowego **wyłącznie po polu
„sygnatura"** oferty (w API: `external.id`). Sygnatura musi być
**dokładnie równa SKU** produktu w ORDLY.

**Dopasowanie po nazwie zostało świadomie odrzucone.** Oferta „Butelka
60 ml szkło + kroplomierz GRATIS" trafiłaby w samą butelkę i cicho
pominęła kroplomierz — a błędne powiązanie odejmuje realny towar
z półki. Lepiej, żeby ORDLY przyznał się do niewiedzy, niż żeby po cichu
psuł stany.

**Praktyczny wniosek:** jeśli po pobraniu dużo ofert zostaje bez
powiązania, sprawdź, czy w Allegro masz wypełnione sygnatury. Po ich
uzupełnieniu wystarczy przycisk **„Dowiąż po sygnaturze"** — nie trzeba
pobierać asortymentu ponownie.

---

## Czego ta paczka NIE zmienia

- **Nie dodaje katalogu w aplikacji mobilnej.** Telefon dalej pokazuje
  sam baner „X ofert sprzedaje się poza magazynem" — tyle że teraz da się
  go zgasić z komputera i baner zniknie sam.
- **Nie odświeża katalogu automatycznie.** Pobieranie jest na żądanie,
  przyciskiem. Automat co kilka minut waliłby w limity zapytań Allegro.
- **Nie wysyła stanów z powrotem na Allegro.** Ruch jest jednokierunkowy:
  Allegro → magazyn. Zmiana stanu w ORDLY nie zmienia liczby sztuk
  w ofercie.
- **Nie rusza istniejących powiązań.** Ręcznie utworzone receptury
  zostają nietknięte — automat ich nie nadpisuje.
