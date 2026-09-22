#!/bin/bash
# ==========================================================
# KafelCenter - Ma'lumotlar Bazasi va Rasmlarni Avtomatik Zaxiralash (Backup)
# Ushbu skript har kuni tunda cron orqali avtomatik ishga tushiriladi
# ==========================================================

BACKUP_DIR="/var/backups/kafel"
DATE=$(date +"%Y-%m-%d_%H-%M-%S")
APP_DIR="/var/www/kafel_magazin"
ARCHIVE_NAME="kafel_backup_${DATE}.tar.gz"

# Zaxira papkasini yaratish
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Zaxiralash boshlandi..."

# SQLite bazasini xavfsiz (hot-backup) nusxalash
TEMP_DB="/tmp/temp_kafel_db.sqlite"
sqlite3 "${APP_DIR}/kafel_database.db" ".backup '${TEMP_DB}'"

# Baza va uploads papkasini arxivga joylash
tar -czf "${BACKUP_DIR}/${ARCHIVE_NAME}" \
    -C /tmp temp_kafel_db.sqlite \
    -C "${APP_DIR}" uploads

rm -f "${TEMP_DB}"

# 30 kundan eski arxivlarni avtomatik o'chirish (disk to'lib qolmasligi uchun)
find "$BACKUP_DIR" -type f -name "kafel_backup_*.tar.gz" -mtime +30 -delete

echo "[$(date)] Zaxira muvaffaqiyatli saqlandi: ${BACKUP_DIR}/${ARCHIVE_NAME}"
