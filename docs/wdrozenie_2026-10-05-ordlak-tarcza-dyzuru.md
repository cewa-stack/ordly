# ORDLY — 5 października 2026: tarcza dyżuru za Ordlakiem (desktop)

Poświata na karcie powitalnej (ekran Start) nie była za Ordlakiem, tylko
obok (sztywne przesunięcia względem karty). Zastąpiła ją „tarcza dyżuru”:
SVG osadzone w pudełku Ordlaka, więc środek tarczy jest środkiem postaci
przy każdej szerokości okna. Dysk pod Ordlakiem, kropkowana orbita z
sekundnikiem (obrót co 60 s) i obwódka z 12 kreskami godzin.

**Tylko desktop (.exe).** Migracja: nie. Backend/Pi: bez zmian. PWA: nie.

## Kontrola (release manager)

- Merge `fix/desktop-karta-powitalna-ordlak` (4104c5b): fast-forward na 5b87e5d, bez 42f9298.
- Desktop `npm run typecheck`: OK.
- Push: `5b87e5d..4104c5b main -> main`. **Commit do rollbacku: `5b87e5d`.**

## Rollback

`git checkout 5b87e5d`, w `desktop/` `npm run dist`, zainstaluj poprzedni .exe, potem `git checkout main`.
