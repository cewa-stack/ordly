# ORDLY — 1 października 2026: szablony maili do hurtowni

Edytor szablonów maila do hurtowni w Ustawieniach desktopu i możliwość
przypisania osobnego szablonu do każdej hurtowni. Wcześniej treść maila
była wpisana na stałe w kodzie.

**Co zmienia ta paczka (tylko desktop):**

1. **Ustawienia → „Szablony maili do hurtowni”** — lista szablonów z
   plakietką „domyślny” i informacją, które hurtownie go używają. Dodanie
   (startuje z kopii domyślnego), edycja, usunięcie, ustawienie jako
   domyślny.
2. **Edytor szablonu** — nazwa i dwa warianty: „Zamówienie” (są zaznaczone
   pozycje) i „Zapytanie” (bez pozycji), każdy z własnym tematem i
   treścią. Znaczniki przyciskami: `{osoba_kontaktowa}`, `{hurtownia}`,
   `{lista_pozycji}`, `{produkty}`, `{data}`. Ostrzeżenie o nieznanym
   znaczniku i o braku `{lista_pozycji}`, podgląd na przykładowych danych.
3. **Edycja hurtowni** — pole „Szablon maila” (Domyślny / inny). Karta
   hurtowni pokazuje, którego szablonu używa.
4. **Okno „Napisz zamówienie”** — mail składa się z przypisanego
   szablonu; pole „Szablon” (gdy jest więcej niż jeden) pozwala jednorazowo
   wybrać inny.
5. Szablonu domyślnego nie da się usunąć. Hurtownie przypisane do
   usuniętego szablonu wracają do domyślnego.

**Migracja bazy: NIE.** **Nowe zmienne `.env`: brak.** **Nowe
zależności: brak.** **Backend / Pi: bez zmian.** **PWA: bez zmian.**
Dane szablonów zapisują się lokalnie w `userData/wholesaler_templates.json`
na komputerze — tak jak hurtownie; przy pierwszym uruchomieniu dotychczasowy
tekst maila staje się szablonem domyślnym, więc nic się nie zmienia, dopóki
nie dodasz własnego.

Źródło: zlecenie z czatu (nie z Notion) — bez pozycji do odhaczenia.

---

## Scalenie i push (wykonane przez release managera)

- Gałąź `feat/szablony-maili-hurtowni`, commit `8ac9b91`.
- Merge do `main`: fast-forward, bez konfliktów.
- `npm run typecheck` (desktop, node + web): OK.
- Backend bez zmian w tej gałęzi — pełne testy backendu i próba migracji
  pominięte celowo (nie ma czego testować); jeden head Alembic (`0013`)
  potwierdzony bezpośrednio przez `ScriptDirectory` (CLI `alembic heads`
  lokalnie zwraca pusty exit 1 — znany lokalny problem środowiska,
  niezwiązany z tą paczką).
- Push: `0460662..8ac9b91 main -> main`.
- **Commit do rollbacku (stan main przed tą paczką): `0460662`.**

## Desktop — nowy `.exe` (do wykonania przez Ciebie)

Zamknij działające ORDLY, potem w `desktop/`:

```bash
cd C:\Users\kukil\Desktop\Projects\toom\desktop
```

```bash
npm run dist
```

Zainstaluj `desktop\release\ORDLY-Setup-0.1.0.exe`. `npm install` nie jest
potrzebne — zależności się nie zmieniły.

## Sprawdzenie po instalacji

- **Ustawienia → „Szablony maili do hurtowni”**: widoczna lista z jednym
  szablonem „domyślny” (treść identyczna jak stara, wpisana na stałe).
- Dodaj nowy szablon, zmień temat/treść, wstaw znacznik `{hurtownia}` —
  podgląd się aktualizuje.
- **Edycja hurtowni**: pole „Szablon maila” pozwala wybrać nowy szablon;
  karta hurtowni pokazuje jego nazwę.
- **„Napisz zamówienie”** dla tej hurtowni: mail używa przypisanego
  szablonu; pole „Szablon” (jeśli masz więcej niż jeden) pozwala
  jednorazowo podmienić.
- Spróbuj usunąć szablon domyślny — ma być zablokowane.
- Usuń przypisany (niedomyślny) szablon — hurtownia wraca do domyślnego.

## Rollback (gdyby coś było nie tak)

Bez migracji i bez zmian na Pi — rollback to tylko desktop:

```bash
git checkout 0460662
```

```bash
cd desktop
```

```bash
npm run dist
```

Zainstaluj starszy `ORDLY-Setup-0.1.0.exe`. Plik
`userData/wholesaler_templates.json` zostaje — nowy kod go po prostu nie
czyta, staremu kodowi nie przeszkadza. Po cofnięciu wróć na `main`:

```bash
git checkout main
```

## Pliki

| Plik | Do czego |
|---|---|
| `desktop/src/main/lib/wholesalerStore.ts` | szablony: wczytanie, zapis, domyślny, usuwanie; `templateId` przy hurtowni |
| `desktop/src/main/ipc/wholesalers.ts`, `desktop/src/preload/index.ts` | IPC `templates`, `saveTemplate`, `setDefaultTemplate`, `deleteTemplate` |
| `desktop/src/renderer/src/lib/wholesalerTemplate.ts` | podstawianie znaczników, wybór szablonu, ostrzeżenia |
| `desktop/src/renderer/src/components/WholesalerTemplatesSettings.tsx` | sekcja w Ustawieniach i edytor (nowy plik) |
| `desktop/src/renderer/src/screens/UstawieniaScreen.tsx`, `HurtowniaScreen.tsx`, `components/WholesalerOrderModal.tsx` | integracja w ekranach |
