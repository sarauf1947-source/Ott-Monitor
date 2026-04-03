#!/bin/bash
# OTT Monitor — Server Health Check Script
# Cron: */5 * * * * /opt/ott_monitor/scripts/health_check.sh >> /var/log/ott-monitor/health.log 2>&1

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000/api/v1}"
WEBHOOK="${WEBHOOK_URL:-}"
HOSTNAME="${HOSTNAME:-$(hostname)}"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S')] $*"; }

notify() {
    local msg="$1"
    log "ALERT: $msg"
    if [ -n "$WEBHOOK" ]; then
        curl -s -X POST "$WEBHOOK" \
            -H "Content-type: application/json" \
            -d "{\"text\":\"🔴 OTT Monitor ALERT on ${HOSTNAME}: ${msg}\"}" \
            >/dev/null 2>&1 || true
    fi
}

check_http() {
    local name="$1" url="$2"
    if curl -sf --max-time 10 "$url" >/dev/null 2>&1; then
        log "OK    $name ($url)"
    else
        notify "$name is DOWN at $url"
        return 1
    fi
}

# Check services
check_http "API Health"    "$API_URL/health"
check_http "Frontend"      "http://localhost:3000"

# Check container health
if command -v docker &>/dev/null; then
    UNHEALTHY=$(docker ps --filter "health=unhealthy" --format "{{.Names}}" | wc -l)
    if [ "$UNHEALTHY" -gt 0 ]; then
        NAMES=$(docker ps --filter "health=unhealthy" --format "{{.Names}}" | tr '\n' ' ')
        notify "$UNHEALTHY unhealthy containers: $NAMES"
    else
        log "OK    All Docker containers healthy"
    fi
fi

log "Health check complete."
