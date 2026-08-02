#!/usr/bin/env bash
#
# Przywraca baze danych z wybranej kopii zapasowej.
#
# WAZNE: Ten skrypt zatrzymuje usluge aplikacji przed przywroceniem
# i uruchamia ja ponownie po zakonczeniu.
#
# Uzycie: ./scripts/restore_db.sh <sciezka_do_kopii_zapasowej>

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${PROJECT_DIR}/data/toom.db"
SERVICE_NAME="toom"

if [ $# -ne 1 ]; then
    echo "Uzycie: $0 <sciezka_do_pliku_kopii_zapasowej>" >&2
    echo "" >&2
    echo "Dostepne kopie zapasowe:" >&2
    ls -lh "${PROJECT_DIR}/backups/"*.db 2>/dev/null || echo "  (brak kopii zapasowych)" >&2
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "BLAD: Plik kopii zapasowej nie istnieje: ${BACKUP_FILE}" >&2
    exit 1
fi

echo "UWAGA: Ta operacja zastapi obecna baze danych zawartoscia kopii:"
echo "  ${BACKUP_FILE}"
read -p "Czy na pewno chcesz kontynuowac? (tak/nie): " CONFIRMATION

if [ "${CONFIRMATION}" != "tak" ]; then
    echo "Operacja anulowana."
    exit 0
fi

echo "Zatrzymywanie uslugi ${SERVICE_NAME}..."
sudo systemctl stop "${SERVICE_NAME}" || echo "Usluga nie byla uruchomiona lub nie istnieje - kontynuuje."

if [ -f "${DB_PATH}" ]; then
    SAFETY_COPY="${DB_PATH}.before_restore_$(date +%Y%m%d_%H%M%S)"
    echo "Tworzenie zapasowej kopii obecnej bazy przed nadpisaniem: ${SAFETY_COPY}"
    cp "${DB_PATH}" "${SAFETY_COPY}"
fi

echo "Przywracanie bazy danych z ${BACKUP_FILE}..."
cp "${BACKUP_FILE}" "${DB_PATH}"

echo "Uruchamianie uslugi ${SERVICE_NAME}..."
sudo systemctl start "${SERVICE_NAME}"

sleep 2
sudo systemctl status "${SERVICE_NAME}" --no-pager

echo ""
echo "Przywracanie zakonczone. Jesli cos poszlo nie tak, kopia bezpieczenstwa"
echo "sprzed przywrocenia znajduje sie pod: ${SAFETY_COPY:-brak (nie bylo wczesniejszej bazy)}"
