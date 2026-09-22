# ORDLY — 22 września 2026: nowe ikony (iPhone + desktop)

**Co zmienia ta paczka:**

1. **Nowa ikona na iPhonie** — Ordlak na ciemnozielonym tle z jednym
   źródłem światła u góry po lewej. Zastępuje rogatą postać na białym tle.
   Stara ikona miała narysowany zaokrąglony kwadrat i biały margines, więc
   iOS nakładał na nią drugą ramkę — nowa to pełny kwadrat, zaokrąglenie
   robi system.
2. **Nowa ikona desktopu** (`.exe`, pasek zadań, pulpit, menu Start).
   Na Windowsie ikona ma własny zaokrąglony kafelek i cienką jasną krawędź,
   żeby nie znikała na ciemnym pasku zadań. Rozmiary 16–32 px mają
   uproszczony rysunek (bez notatnika), bo pomniejszony pełny rysunek miał
   tam oczy po dwa piksele.
3. **Ta sama grafika w powiadomieniach push** — iOS pokazuje przy każdym
   powiadomieniu ikonę aplikacji.

**Czego ta paczka NIE zmienia:** treści powiadomień. Projekt nowych treści
(`backend/docs/projekt-powiadomien-push-nokturn.html`) czeka na Twoją
akceptację. Kod propozycji jest już w katalogu, ale **nie jest podpięty do
wysyłki** — telefon dostaje dokładnie te same powiadomienia co dziś.

Backend nie wymaga migracji ani nowych zależności.

---

## CZĘŚĆ A — scal i wypchnij (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

Na liście zmian zobaczysz też usunięte pliki `bot_ordlak/mascot_*.png`
i `mascot_*-removebg-preview.png` — tych nie usuwałem ja. Nic w kodzie ich
nie używa (sprawdzone), więc możesz je zatwierdzić albo przywrócić — to
Twoja decyzja, nie jest częścią tej łatki.

```bash
git checkout main
```

```bash
git merge ikona-ios
```

Ma napisać `Fast-forward`. Jeśli zobaczysz `CONFLICT` — zatrzymaj się
i wklej mi output.

```bash
git push
```

---

## CZĘŚĆ B — Raspberry Pi: kod (przez SSH)

Kod backendu zmienia się tylko o niepodpięte buildery i dokumentację, więc
to krok porządkowy — żeby na Pi leżało to samo co w `main`.

```bash
ssh cewastack2@cewastack2
```

```bash
cd ~/ordly/backend
```

```bash
git status --short
```

Jeśli pokaże zmienione pliki, cofnij je (nie rusza `.env` ani `data/`):

```bash
git restore .
```

```bash
git pull
```

Restartu nie robisz tutaj — zrobi go komenda z części C.

---

## CZĘŚĆ C — telefon: nowa paczka PWA

### C1. Zbuduj (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom\mobile
```

```bash
npx expo export -p web
```

Sprawdź, że nowa ikona jest w paczce:

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

Ma pokazać `/home/cewastack2/ordly/webapp_dist`. Jeśli pokaże coś innego,
podmień ścieżkę w komendzie niżej.

```bash
ssh cewastack2@cewastack2 "rm -rf ~/ordly/webapp_dist/* && tar -xzf ~/mobile-dist.tgz -C ~/ordly/webapp_dist && chmod -R a+rX ~/ordly/webapp_dist && rm ~/mobile-dist.tgz && sudo systemctl restart ordly"
```

```bash
ssh cewastack2@cewastack2 "sudo systemctl status ordly --no-pager | head -3"
```

Ma być `active (running)`.

### C4. Podmień ikonę na iPhonie

> ⚠️ **iOS zapamiętuje ikonę w chwili dodania do ekranu głównego i nigdy
> jej sam nie odświeża.** Bez tego kroku zostanie stara.

1. Przytrzymaj ikonę ORDLY → **Usuń aplikację** → **Usuń z ekranu
   początkowego**. (Usuwa tylko skrót — dane zostają na Pi.)
2. Otwórz **Safari** i wejdź na `https://cewastack2.tail7f5a20.ts.net`.
3. **Udostępnij** → **Do ekranu początkowego** → **Dodaj**.
4. Otwórz ORDLY z nowej ikony i zaloguj się, jeśli poprosi.
5. **Włącz powiadomienia ponownie**: Ustawienia w ORDLY → Powiadomienia.
   Nowa instalacja PWA to dla iOS nowa aplikacja — stara subskrypcja nie
   przechodzi.

Jeśli na ekranie „Dodaj do ekranu początkowego" widać jeszcze starą ikonę:
Ustawienia iPhone'a → Safari → **Wyczyść historię i dane witryn**, potem
krok 2 od nowa.

---

## CZĘŚĆ D — desktop: nowy `.exe`

Instalator jest **już zbudowany** z tej łatki:
`desktop\release\ORDLY-Setup-0.1.0.exe` (22 września, 10:28). Możesz go
zainstalować od razu.

Jeśli wolisz zbudować sam (np. po scaleniu na innym komputerze):

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm install
```

```bash
npm run dist
```

Zamknij działające ORDLY i zainstaluj `desktop\release\ORDLY-Setup-0.1.0.exe`.

### D1. Windows też trzyma ikony w pamięci

Jeśli po instalacji skrót na pulpicie albo przypięta ikona na pasku zadań
dalej pokazuje starą grafikę, to pamięć podręczna ikon Windowsa, nie
nieudana instalacja:

1. Odepnij ORDLY z paska zadań i przypnij ponownie z menu Start.
2. Jeśli skrót na pulpicie dalej jest stary — usuń go i utwórz nowy
   z menu Start (przeciągnij).

---

## Sprawdzenie

- **iPhone, ekran główny:** ciemnozielony kwadrat bez białej obwódki,
  turkusowa maskotka z anteną i notatnikiem.
- **iPhone, powiadomienie:** przy następnym push ta sama maskotka w dymku.
- **Windows, pasek zadań:** ciemny kafelek z jasną krawędzią, maskotka
  z anteną i dwojgiem oczu — czytelna także na ciemnym pasku.
- **Windows, Eksplorator** (widok „Duże ikony”): pełny rysunek z notatnikiem.

## Pliki

| Plik | Do czego |
|---|---|
| `mobile/public/apple-touch-icon.png` (180 px) | ekran główny iPhone'a |
| `mobile/public/icon-192.png`, `icon-512.png` | manifest PWA |
| `mobile/public/icon.png` (1024 px) | ikona powiadomień push |
| `mobile/assets/icon.png` + `icon.svg` | natywny build (EAS) i źródło |
| `desktop/build/icon.ico` (16–256 px, 8 rozmiarów) | `.exe`, pasek zadań, pulpit |
| `desktop/build/icon.svg`, `icon-small.svg` | źródła: pełny i uproszczony rysunek |
| `desktop/build/make-icon.mjs` | `node build/make-icon.mjs` odtwarza `.ico` ze źródeł |
