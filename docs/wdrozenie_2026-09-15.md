# ORDLY — 15 września 2026: automatyczne wykrywanie numeru przesyłki InPost

**Co zmienia ta paczka:**

1. **ORDLY sam zauważy, że paczka została nadana** — gdy na Allegro pojawi
   się numer przesyłki InPost (Allegro dopisuje go do zamówienia
   automatycznie), aplikacja **lokalnie** pokaże zamówienie jako „Wysłane"
   (pigułka, licznik „Do spakowania", oś czasu w szczegółach, filtry,
   eksport CSV) — bez czekania, aż ręcznie zmienisz status na Allegro.
2. Nowy cykliczny job sprawdza otwarte zamówienia **co 5 minut**
   (`CHECK_WAYBILLS_INTERVAL_SECONDS`, domyślnie 300 — nie trzeba nic
   ustawiać w `.env`, chyba że chcesz inny odstęp).
3. **Zakres celowo tylko lokalny** — nic nie jest zapisywane z powrotem na
   Allegro. Realny status realizacji na Allegro (i to, co widzi kupujący)
   zmieniasz tak jak dotychczas, ręcznie.

**Bez migracji bazy.** Numer przesyłki jest czytany tą samą drogą, co przy
ręcznej komendzie/przycisku „Sprawdź przesyłkę" — nowy job tylko wywołuje ją
sam, zamiast czekać na Ciebie.

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
git commit -m "Automatyczne wykrywanie numeru przesylki InPost -> lokalne wyslano

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
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

### B2. Sprawdź, czy na Pi nie ma lokalnych zmian w kodzie

```bash
git status --short
```

Jeśli pokaże zmienione pliki, cofnij je (nie rusza `.env`):

```bash
git restore .
```

### B3. Pobierz, zsynchronizuj zależności i zrestartuj

**Migracji nie ma** — pomiń `alembic upgrade`. Historia repo tym razem NIE
była przepisywana, więc zwykłe `git pull` zadziała.

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
sudo systemctl status ordly --no-pager
```

Ma być `active (running)`.

### B4. Potwierdź, że nowy job wystartował

```bash
journalctl -u ordly --since "2 min ago" | grep -i "przesyłek"
```

Ma pojawić się linia „Zarejestrowano job sprawdzania numerów przesyłek co
300s".

---

## CZĘŚĆ C — telefon: nowa wersja aplikacji (PWA)

> **Sam `git pull` na Pi NIE aktualizuje aplikacji na telefonie.** Bez tego
> kroku pigułka na telefonie nie pokaże „Wysłane" przy wykrytej przesyłce.

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

## CZĘŚĆ E — sprawdzenie

- **Bez czekania na prawdziwe zamówienie:** w logach po restarcie (B4)
  powinna pojawić się linia o zarejestrowaniu joba. Sam efekt (pigułka
  „Wysłane") zobaczysz dopiero przy pierwszym zamówieniu, które dostanie
  numer InPost po tej aktualizacji — job sprawdza otwarte zamówienia co
  5 minut, więc może minąć chwila.
- **Desktop i telefon, Zamówienia:** gdy Allegro dopisze numer przesyłki do
  zamówienia (bez zmiany statusu realizacji), w ciągu max. 5 minut pigułka
  ma pokazać „Wysłane", a zamówienie ma zniknąć z „Do spakowania" — mimo że
  na samym Allegro status realizacji się nie zmienił.
- **Ręczne „Oznacz jako wysłane"** działa dokładnie tak jak wcześniej i
  nadal zapisuje status na Allegro — ta zmiana go nie dotyka.
- Gdyby coś nie zgadzało się z realnym stanem na Allegro:
  `journalctl -u ordly -f | grep -i przesył` pokaże, co job aktualnie robi.
