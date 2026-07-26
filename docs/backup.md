# Backup i odzyskiwanie - ORDLY

## Automatyczny backup

Codziennie o 3:00 (czas polski) `BackupService` tworzy spójną kopię
bazy danych przez natywne `VACUUM INTO` SQLite, bezpieczne nawet
podczas aktywnego zapisu przez inne połączenia.

## Ręczny backup

```bash
# Przez API
curl -X POST http://127.0.0.1:8000/backup/trigger

# Przez skrypt niezależny od aplikacji Python
./scripts/backup_db.sh
```

## Odzyskiwanie

```bash
./scripts/restore_db.sh backups/ordly_manual_20260717_030000.db
```

Skrypt automatycznie:
1. Zatrzymuje usługę `ordly`.
2. Tworzy kopię bezpieczeństwa obecnej bazy (na wypadek pomyłki).
3. Podmienia bazę na wybraną kopię.
4. Uruchamia usługę ponownie.

## Retencja

Kopie starsze niż `BACKUP_RETENTION_DAYS` (domyślnie 30 dni) są
automatycznie usuwane po każdym nowym backupie.
