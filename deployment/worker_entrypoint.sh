#!/bin/sh

TOTAL_WORKERS=${TOTAL_WORKERS:-1}

if [ -n "${WORKER_ID:-}" ]; then
    export WORKER_ID
    echo "Starting worker with explicit WORKER_ID=${WORKER_ID} of ${TOTAL_WORKERS}"
else
    echo "Starting worker with Redis shard auto-discovery across ${TOTAL_WORKERS} shard(s)"
fi

export TOTAL_WORKERS
exec python -m workers.monitor_worker
