# ORDLY — 22 września 2026: nowa ikona aplikacji (iOS)

**Co zmienia ta paczka:**

1. **Nowa ikona w stylu Nokturn** — Ordlak (ta sama maskotka co w
   aplikacji, w stanie spoczynku) na ciemnozielonym tle z jednym źródłem
   światła u góry po lewej. Zastępuje starą ikonę z rogatą postacią na
   białym tle.
2. **Poprawiona ikona ekranu głównego iPhone'a.** Stara miała narysowany
   zaokrąglony kwadrat i biały margines, więc iOS nakładał na nią drugą
   ramkę. Nowa to pełny kwadrat bez przezroczystości — zaokrąglenie
   robi system.
3. **Ta sama grafika w powiadomieniach push** (korzystają z `/icon.png`).

Backend się nie zmienia — **nie trzeba nic robić na Pi poza podmianą
paczki PWA.**

---

## CZĘŚĆ A — scal i wypchnij (na komputerze)

```bash
cd C:\Users\kukil\Desktop\Projects\toom
```

```bash
git checkout main
```

```bash
git merge ikona-ios
```

```bash
git push
```

---

## CZĘŚĆ B — nowa paczka PWA

### B1. Zbuduj (na komputerze)

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

### B2. Spakuj i wyślij

**Nie używaj `Compress-Archive`** — gubi bit wykonywalności na katalogach.

```bash
tar -czf mobile-dist.tgz -C dist .
```

```bash
scp mobile-dist.tgz cewastack2@cewastack2:~/
```

### B3. Podmień paczkę na Pi

```bash
ssh cewastack2@cewastack2 "grep WEB_APP_DIST_PATH ~/ordly/backend/.env"
```

Ma pokazać `/home/cewastack2/ordly/webapp_dist`. Jeśli pokaże coś innego,
podmień ścieżkę w komendzie niżej.

```bash
ssh cewastack2@cewastack2 "rm -rf ~/ordly/webapp_dist/* && tar -xzf ~/mobile-dist.tgz -C ~/ordly/webapp_dist && chmod -R a+rX ~/ordly/webapp_dist && rm ~/mobile-dist.tgz && sudo systemctl restart ordly"
```

---

## CZĘŚĆ C — podmień ikonę na iPhonie

> ⚠️ **iOS zapamiętuje ikonę w chwili dodania do ekranu głównego i nigdy
> jej sam nie odświeża.** Wdrożenie na Pi nie wystarczy — stara ikona
> zostanie na telefonie, dopóki nie dodasz aplikacji od nowa.

1. Przytrzymaj ikonę ORDLY na ekranie głównym → **Usuń aplikację** →
   **Usuń z ekranu początkowego**. (To usuwa tylko skrót — dane i
   logowanie zostają na Pi.)
2. Otwórz **Safari** i wejdź na `https://cewastack2.tail7f5a20.ts.net`.
3. Przycisk **Udostępnij** → **Do ekranu początkowego** → **Dodaj**.
4. Otwórz ORDLY z nowej ikony i zaloguj się, jeśli poprosi.
5. **Powiadomienia push trzeba włączyć ponownie**: Ustawienia w ORDLY →
   Powiadomienia. Nowa instalacja PWA to dla iOS nowa aplikacja, więc
   stara subskrypcja nie przechodzi.

Jeśli na ekranie „Dodaj do ekranu początkowego" widać jeszcze starą ikonę,
Safari ma ją w pamięci podręcznej: Ustawienia iPhone'a → Safari →
**Wyczyść historię i dane witryn**, potem krok 2 od nowa.

---

## Sprawdzenie

- Na ekranie głównym: ciemnozielony kwadrat z zaokrągleniem systemowym,
  bez białej obwódki, turkusowa maskotka z anteną i notatnikiem.
- W Spotlight i w Ustawieniach (małe rozmiary) maskotka ma nadal
  widoczne oczy.
- Następne powiadomienie push przychodzi z nową grafiką.

## Pliki

| Plik | Do czego |
|---|---|
| `mobile/public/apple-touch-icon.png` (180 px) | ikona ekranu głównego iPhone'a |
| `mobile/public/icon-192.png`, `icon-512.png` | manifest PWA (Android, Chrome) |
| `mobile/public/icon.png` (1024 px) | ikona powiadomień push |
| `mobile/assets/icon.png` (1024 px) | natywny build przez EAS / App Store |
| `mobile/assets/icon.svg` | źródło — z niego da się wygenerować każdy rozmiar |
