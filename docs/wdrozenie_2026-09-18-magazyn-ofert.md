# ORDLY — 18 września 2026: magazyn na ofertach zamiast produktów SKU

**Co zmienia ta paczka:**

1. **Magazyn to teraz lista tego, co masz wystawione.** Oferty pobrane
   z marketplace'ów, przy każdej miniatura, tytuł, cena i ikona kanału.
   Przycisk „Synchronizuj" dociąga nowo wystawione oferty.
2. **Ilość wpisujesz ręcznie, wprost przy ofercie** (tylko desktop). Każdy
   wpis zapisuje się w historii — data, zmiana, powód.
3. **Zniknęło automatyczne zdejmowanie stanu.** Nie ma już produktów SKU,
   progów minimalnych, receptur, powiązań oferta↔produkt, listy zakupowej
   ani alertu „niski stan". Sprzedaż niczego nie odejmuje.
4. **Na telefonie Magazyn jest czystym podglądem** — miniatura, tytuł,
   cena, ikona kanału i synchronizacja. Ilości na telefonie nie ma.
5. **Hurtownia ma własną listę pozycji** (nazwa + ilość), wpisywaną
   ręcznie w edycji hurtowni. Nie ma już nic wspólnego z Magazynem.
6. Telegram: `/stock` pokazuje teraz oferty i wpisane ilości, tylko do
   odczytu (podkomendy `set`/`add`/`remove`/`min`/`link` zniknęły).

---

## ⚠️ Zanim zaczniesz — to kasuje dane z bazy

Migracja `0012` **usuwa tabele starego magazynu**: `inventory_items`,
`inventory_movements`, `offer_links`, `stock_syncs`. Stanów **nie da się
przenieść** do nowego modelu — były mieszaniną liczb pilnowanych i
niepilnowanych, więc ilości startują puste (`NULL` = „nie wpisano") i
uzupełnia się je ręcznie z desktopu.

Cofnięcie migracji odtwarza **puste** tabele, nie ich zawartość. Dlatego
krok **B2 (kopia bazy)** nie jest opcjonalny.

Jeśli chcesz zachować stare stany na papierze, **zanim zaczniesz** wejdź
w obecnej wersji aplikacji w Magazyn i zrób zrzut ekranu listy — potem ta
lista już nie istnieje.

---

## CZĘŚĆ A — commit i push (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

```bash
git add -A
```

Sprawdź, czy na liście nie ma nic niespodziewanego (np. plików z sekretami):

```bash
git status --short
```

```bash
git commit -m "Magazyn na ofertach z reczna iloscia zamiast produktow SKU

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

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

### B2. Zrób kopię bazy (nie pomijaj tego kroku)

```bash
cp data/ordly.db ~/ordly-przed-magazynem-2026-09-18.db
```

Sprawdź, że kopia naprawdę powstała i nie jest pusta:

```bash
ls -lh ~/ordly-przed-magazynem-2026-09-18.db
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

### B5. Uruchom migrację

Zatrzymaj usługę, żeby nic nie pisało do bazy w trakcie:

```bash
sudo systemctl stop ordly
```

```bash
uv run alembic upgrade head
```

Ostatnia linia ma zawierać `Running upgrade 0011 -> 0012`. Jeśli pojawi
się błąd — **nie restartuj usługi**, wklej mi cały output.

```bash
sudo systemctl start ordly
```

```bash
sudo systemctl status ordly --no-pager
```

Ma być `active (running)`.

### B6. Potwierdź, że baza jest na nowej wersji

```bash
uv run alembic current
```

Ma pokazać `0012 (head)`.

```bash
journalctl -u ordly --since "2 min ago" | grep -i "error\|traceback"
```

Brak wyniku = dobrze. Jeśli coś się wypisze, wklej mi to.

---

## CZĘŚĆ C — telefon: nowa wersja aplikacji (PWA)

> **Sam `git pull` na Pi NIE aktualizuje aplikacji na telefonie.** Bez tego
> kroku telefon dalej pokaże stary ekran magazynu i wywali się na
> nieistniejącym już `/stock`.

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

```bash
ssh cewastack2@cewastack2 "ls -lh ~/mobile-dist.tgz"
```

Jeśli `No such file` — zatrzymaj się tutaj.

### C3. Podmień paczkę na Pi

```bash
ssh cewastack2@cewastack2 "rm -rf ~/ordly/webapp_dist/* && tar -xzf ~/mobile-dist.tgz -C ~/ordly/webapp_dist && chmod -R a+rX ~/ordly/webapp_dist && rm ~/mobile-dist.tgz && sudo systemctl restart ordly"
```

### C4. Odśwież PWA na telefonie

Zamknij aplikację ORDLY na telefonie **całkowicie** (przesuń w górę
z listy aplikacji) i otwórz ponownie. Sam powrót do niej pokaże starą
wersję z pamięci.

---

## CZĘŚĆ D — nowy `.exe` (na komputerze)

Zamknij działającą aplikację ORDLY, potem:

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm run dist
```

Zainstaluj `desktop\release\ORDLY-Setup-0.1.0.exe`.

---

## CZĘŚĆ E — pierwsze uruchomienie po aktualizacji

### E1. Magazyn — pobierz katalog i wpisz stany

1. Desktop → **Magazyn** → **Synchronizuj**. Lista zapełni się ofertami
   wystawionymi na marketplace'ach.
2. Przy każdej ofercie, przy której chcesz pilnować stanu, kliknij
   **„Wpisz stan"** i podaj ilość z półki.
3. Oferta bez wpisanej ilości zostaje pusta — to celowe. Puste znaczy
   „nigdy nie liczyłem" i to **nie to samo co 0** („policzyłem, nie ma").
4. Później ilość zmienia się strzałkami przy liczbie albo kliknięciem
   w samą liczbę (wtedy wpisujesz nową wartość i powód).
5. Przycisk **„Historia"** przy ofercie pokazuje wszystkie Twoje wpisy.

### E2. Hurtownia — wpisz listy pozycji na nowo

Hurtownie i historia wysłanych maili zostają, ale **stare powiązania SKU
zniknęły** — lista pozycji każdej hurtowni jest pusta.

W każdej hurtowni kliknij ołówek → sekcja **„Co się tu zamawia"** →
wpisz nazwę pozycji i ilość, którą zwykle bierzesz → **Zapisz**.

Przy pisaniu maila wszystkie pozycje są zaznaczone z góry; odznaczasz to,
czego akurat nie potrzebujesz. Mail bez pozycji nadal działa (zapytanie
o cennik czy termin).

---

## CZĘŚĆ F — sprawdzenie

- **Desktop, Magazyn:** lista ofert z miniaturami i cenami, u góry „Pobrano
  [data]". Po wpisaniu ilości „Historia" pokazuje wpis z powodem.
- **Telefon, Magazyn:** ta sama lista, bez ilości i bez steppera.
  Synchronizacja działa z telefonu.
- **Start (desktop):** druga kafelka pokazuje liczbę wystawionych ofert
  (zamiast dawnego licznika niskiego stanu). W pasku bocznym przy Magazynie
  nie ma już czerwonej kropki.
- **Statystyki:** panel „Prognoza wyczerpania zapasu" zniknął — nie ma już
  danych, z których go liczono.
- **Ustawienia:** sekcja „Progi niskiego stanu" zniknęła.
- **Telegram:** `/stock` ma wypisać oferty z ilościami. `/stock butelka`
  zawęża do pasujących.
- **Powiadomienia push:** nie przychodzi już „niski stan" ani „pozycja bez
  powiązania" — te dwa typy zostały usunięte. Reszta (nowe zamówienie,
  zwrot, dyskusja, awaria poczty, Allegro Lokalnie, OLX) działa bez zmian.

---

## Gdyby coś poszło nie tak

Logi backendu na żywo:

```bash
journalctl -u ordly -f
```

Powrót do stanu sprzed aktualizacji — **kolejność ma znaczenie**, jedna
komenda na raz:

```bash
sudo systemctl stop ordly
```

```bash
cd ~/ordly/backend
```

```bash
cp ~/ordly-przed-magazynem-2026-09-18.db data/ordly.db
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
