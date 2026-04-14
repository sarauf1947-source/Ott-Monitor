#!/bin/bash
# OTT Monitor health check - add to cron: */5 * * * * /opt/ott_monitor/scripts/health_check.sh
set -euo pipefail
API_URL="${API_URL:-http://localhost:8000/api/v1}"
WEBHOOK="${WEBHOOK_URL:-}"
log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*"; }
notify() { log "ALERT: $1"; [ -n "$WEBHOOK" ] && curl -s -X POST "$WEBHOOK" -H "Content-type: application/json" -d "{\"text\":\"OTT Monitor ALERT: $1\"}" >/dev/null 2>&1 || true; }
check() { curl -sf --max-time 10 "$2" >/dev/null 2>&1 && log "OK $1" || { notify "$1 is DOWN at $2"; return 1; }; }
check "API"      "$API_URL/health"
check "Frontend" "http://localhost:3000"
command -v docker &>/dev/null && { U=$(docker ps --filter "health=unhealthy" --format "{{.Names}}" | wc -l); [ "$U" -gt 0 ] && notify "$U unhealthy containers" || log "OK containers"; }
log "Health check complete."
