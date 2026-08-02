# Deployment - ORDLY

## Wdrożenie natywne (systemd) - zalecane na Raspberry Pi

### Krok 1: Instalacja zależności

```bash
cd ~/ordly
git pull
uv sync
uv run alembic upgrade head
```

### Krok 2: Test ręczny

```bash
uv run python -m app.main
```

Sprawdź w innym terminalu: `curl http://127.0.0.1:8000/health`
oraz `/start` w Telegramie do bota ORDLY.

### Krok 3: Instalacja usługi systemd

```bash
sudo cp scripts/ordly.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ordly
sudo systemctl start ordly
```

**Zamień w pliku `.service`** użytkownika `pi` oraz ścieżkę
`/home/pi/ordly` na rzeczywiste wartości ze swojego
systemu (`whoami`, `pwd`).

### Krok 4: Weryfikacja

```bash
sudo systemctl status ordly
journalctl -u ordly -f
```

### Krok 5: Test restartu

```bash
sudo systemctl restart ordly
sudo reboot
```

Po restarcie: `sudo systemctl status ordly` powinno
pokazywać `active (running)` bez ręcznej interwencji.

## ORDLY Mobile (PWA) razem z backendem

Żeby appka mobilna działała 24/7 bez trzymania komputera włączonego,
backend potrafi serwować jej zbudowaną (statyczną) wersję z tego samego
portu co API — pełna instrukcja: [01_app.md §6.5](01_app.md#65-wdrożenie-247-na-raspberry-pi-bez-zależności-od-komputera).
Skrót: `npx expo export -p web` w `mobile/`, skopiuj `dist/` na Pi,
ustaw `WEB_APP_DIST_PATH` w `.env`, zrestartuj usługę.

## Wdrożenie przez Docker (alternatywa)

```bash
cd docker
docker compose up -d --build
docker compose logs -f
```

**Uwaga:** nie uruchamiaj równolegle systemd i Dockera - obie ścieżki
próbowałyby jednocześnie odpytywać Allegro API i wysyłać powiadomienia
Telegram, co prowadziłoby do zdublowanych wiadomości.
