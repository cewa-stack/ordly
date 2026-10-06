# ORDLY — 6 października 2026: prosty krąg za Ordlakiem (desktop)

Tarcza dyżuru (orbita, sekundnik, 12 kresek) wyglądała jak kompas. Zastąpił
ją jeden płaski krąg 150 px, symetryczny i wyśrodkowany na Ordlaku: tło o ton
jaśniejsze od karty i cienka obwódka, bez ruchu. Ordlak podniesiony o 5 px,
żeby widoczna figura była dokładnie w środku kręgu.

**Tylko desktop (.exe).** Migracja: nie. Backend/Pi: bez zmian. PWA: nie.

## Kontrola (release manager)

- Merge `fix/desktop-karta-powitalna-minimal` (6b47554): fast-forward na bed2c1f, bez 42f9298.
- Desktop `npm run typecheck`: OK.
- Push: `bed2c1f..6b47554 main -> main`. **Commit do rollbacku: `bed2c1f`.**
- Jeden nowy .exe obejmuje też zmiany desktopowe z paczki hurtowni Huba (`docs/wdrozenie_2026-10-06-control-hub-hurtownie.md`), jeśli jeszcze nie był instalowany.

## Rollback

`git checkout bed2c1f`, w `desktop/` `npm run dist`, zainstaluj poprzedni .exe, potem `git checkout main`.
