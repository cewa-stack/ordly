# ORDLY — 5 października 2026: ekran „Historia sprzedaży” na Control Hubie

Nowy, piąty ekran Huba (między Statystykami a Statusem): zamówienia jednego
dnia (godzina, kanał, produkt, kwota), podzielone na dni, z sumą dnia bez
anulowanych. Hub nie trzyma historii — przy każdym naciśnięciu prosi ORDLY
o jeden ekran.

- Hub -> ORDLY: `ordly/hub/history/get` `{date?, page?}`
- ORDLY -> Hub: `ordly/history/day` (5 zamówień na stronę, polska doba)

**Migracja: NIE. Nowe `.env`: brak. Nowe zależności: brak. PWA/desktop: nie.**
Backend na Pi: pull + restart. Firmware Huba (`ordly_control_hub/`, poza gitem): wgrać wersję 1.0.1 z ekranem Historia.

## Kontrola (release manager)

- Merge `build/control-hub-historia` (e69a3e1): fast-forward na 0153258.
- pytest 775 passed; ruff OK; mypy 35 znanych błędów; jeden head `0016`.
- Push: `0153258..e69a3e1 main -> main`. **Commit do rollbacku tej paczki: `0153258`.**
- Wdrażane razem z paczką statusów/zwrotów (`docs/wdrozenie_2026-10-05-statusy-zamowien-i-rejestr-zwrotow.md`, rollback `063f4bb`), jeśli ta jeszcze nie była wgrana.

## Rollback

Tylko backend, bez migracji: `git checkout 0153258` na Pi, `uv sync`, restart usługi. Hub po 4 s pokaże „ORDLY nie odpowiada na prośbę o historię”, reszta działa.
