#!/bin/bash
# OTT Monitor — Automated Database Backup
# Cron: 30 2 * * * /opt/ott_monitor/scripts/backup_db.sh >> /var/log/ott-monitor/backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/data/ott/backups}"
COMPOSE_FILE="${COMPOSE_FILE:-/opt/ott_monitor/deployment/docker-compose.yml}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/ott_backup_${DATE}.sql.gz"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*"; }

mkdir -p "$BACKUP_DIR"

log "Starting backup → $BACKUP_FILE"

docker compose -f "$COMPOSE_FILE" exec -T timescaledb \
    pg_dump -U ott_user ott_monitor \
    | gzip > "$BACKUP_FILE"

SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
log "Backup complete: $BACKUP_FILE ($SIZE)"

# Remove old backups
REMOVED=$(find "$BACKUP_DIR" -name "ott_backup_*.sql.gz" -mtime "+${RETENTION_DAYS}" -print -delete | wc -l)
[ "$REMOVED" -gt 0 ] && log "Removed $REMOVED backup(s) older than ${RETENTION_DAYS} days"

log "Done."
