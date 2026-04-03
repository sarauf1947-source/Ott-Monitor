#!/bin/sh
# Worker entrypoint — assigns WORKER_ID from Docker Swarm task slot or hostname hash
# When using docker compose --scale worker=N, each replica gets a unique WORKER_ID

WORKER_ID=${WORKER_ID:-0}

# If running under Docker Swarm or Compose with service index, use it
if [ -n "$HOSTNAME" ] && [ -z "$WORKER_ID" ]; then
    # Extract trailing number from hostname (e.g., ott_monitor_worker_3 -> 2 zero-indexed)
    SUFFIX=$(echo "$HOSTNAME" | grep -oE '[0-9]+$')
    if [ -n "$SUFFIX" ]; then
        WORKER_ID=$((SUFFIX - 1))
    fi
fi

export WORKER_ID
export TOTAL_WORKERS=${TOTAL_WORKERS:-15}

echo "Starting worker ID=${WORKER_ID} of ${TOTAL_WORKERS} total workers"
exec python -m workers.monitor_worker
