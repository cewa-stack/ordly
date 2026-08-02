#!/usr/bin/env bash
#
# Tworzy kopie zapasowa bazy danych niezaleznie od dzialania aplikacji
# Python (TOOM) - uzywa bezposrednio `sqlite3`
# CLI z komenda .backup, bezpieczna nawet gdy aplikacja jednoczesnie
# pisze do bazy.
#
# Uzycie: ./scripts/backup_db.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${PROJECT_DIR}/data/toom.db"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${BACKUP_DIR}/toom_manual_${TIMESTAMP}.db"

if [ ! -f "${DB_PATH}" ]; then
    echo "BLAD: Nie znaleziono bazy danych pod ${DB_PATH}" >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"

echo "Tworzenie kopii zapasowej: ${BACKUP_PATH}"
sqlite3 "${DB_PATH}" ".backup '${BACKUP_PATH}'"

if [ -f "${BACKUP_PATH}" ]; then
    SIZE=$(du -h "${BACKUP_PATH}" | cut -f1)
    echo "Kopia zapasowa utworzona pomyslnie (${SIZE})."
else
    echo "BLAD: Kopia zapasowa nie zostala utworzona." >&2
    exit 1
fi

# Usuwanie kopii starszych niz 30 dni (spojne z BACKUP_RETENTION_DAYS z .env)
find "${BACKUP_DIR}" -name "toom_*.db" -mtime +30 -delete
echo "Stare kopie zapasowe (starsze niz 30 dni) zostaly usuniete."
