# ORDLY — 7 października 2026: alert o paczce InPost od F.H.P. MAIK-POL

Jednorazowe powiadomienie, gdy przyjdzie mail InPost „Potwierdzenie nadania
przesyłki” o paczce od F.H.P. MAIK-POL: pomarańczowy wpis „Paczka z hurtowni”
na Control Hubie (zamyka go tylko OK) i jeden push na telefonie. Działa na Pi
w jobie poczty co 5 min; nadawca `info@paczkomaty.pl` wpisany na stałe.
Ten sam mail nigdy nie daje drugiego alertu (tabela `processed_parcel_mails`).
Maile InPost nie trafiają do zakładki Poczta. Pierwsze uruchomienie przegląda
3 dni wstecz. Telegram i desktop bez zmian.

**Migracja: TAK** (`0017 -> 0018`). Nowe `.env`: brak. Nowe zależności: brak.
Backend na Pi: tak. PWA: nie. Desktop: nie. Firmware Huba 1.0.2 (lokalny folder).

## Kontrola (release manager)

- Merge `feat/mail-inpost-maik-pol` (5b5b031): fast-forward na 2f1fde5, bez 42f9298.
- pytest 825 passed (test zależny od godziny padał tylko o 0:22, o 8:24 przechodzi); ruff OK; mypy 35 znanych błędów; jeden head `0018`.
- Migracja na czystej bazie: upgrade, downgrade do 0017, upgrade OK.
- Push: `2f1fde5..5b5b031 main -> main`. **Commit do rollbacku: `2f1fde5`.**
- Niesprawdzone lokalnie: prawdziwy mail z Gmaila (HTML InPost może się różnić od odtworzonego fixture), działanie na Pi.

## Weryfikacja na Pi

Logi z „Paczki od hurtowni:”, tabela `processed_parcel_mails`; wartość `outcome`
`other_wholesaler` / `no_number` przy prawdziwym mailu MAIK-POL = parser do
poprawki (potrzebny oryginał `.eml`).

## Rollback

`sudo systemctl stop ordly`, `cd ~/ordly/backend`, `uv run alembic downgrade 0017`
(usuwa tylko `processed_parcel_mails`), `git checkout 2f1fde5`, `uv sync`,
`sudo systemctl start ordly`, potem `git checkout main`.
