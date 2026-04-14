# -*- coding: utf-8 -*-
"""System health metrics endpoint."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import psutil
from fastapi import APIRouter, Depends, Query

from api.auth.auth_deps import get_current_user
from config import settings
from utils.cache import redis_client

metrics_router = APIRouter(prefix="/api/v1/system", tags=["System Metrics"])
logger = logging.getLogger(__name__)

_HISTORY_KEY = "ott:system:metrics:history"
_LAST_NET_KEY = "ott:system:metrics:last_net"
_MAX_HISTORY_POINTS = 1440


@metrics_router.get("/health")
async def system_health_no_auth():
    """Unauthenticated ping - safe for load balancers."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


async def _read_worker_details() -> tuple[list[dict], bool]:
    worker_details = []
    redis_ok = False
    try:
        await redis_client.ping()
        redis_ok = True
        keys = await redis_client.keys("worker:status:*")
        for key in keys:
            data = await redis_client.hgetall(key)
            if not data:
                continue
            worker_details.append({
                "worker_id": data.get("worker_id", key.split(":")[-1]),
                "shard_id": int(data.get("shard_id", 0)),
                "streams_assigned": int(data.get("streams_assigned", 0)),
                "streams_ok": int(data.get("streams_ok", 0)),
                "streams_error": int(data.get("streams_error", 0)),
                "last_cycle_sec": float(data.get("last_cycle_sec", 0)),
                "last_updated": data.get("last_updated", ""),
                "notification_queue_depth": int(data.get("notification_queue_depth", 0)),
                "probe_concurrency": int(data.get("probe_concurrency", 0)),
            })
        worker_details.sort(key=lambda item: (item["shard_id"], item["worker_id"]))
    except Exception as exc:
        logger.warning("Failed to read worker metrics from Redis: %s", exc)
    return worker_details, redis_ok


async def _build_metrics_payload() -> dict:
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    now = datetime.now(timezone.utc)

    worker_details, redis_ok = await _read_worker_details()
    queue_depth = sum(worker["notification_queue_depth"] for worker in worker_details)
    workers_assigned = sum(worker["streams_assigned"] for worker in worker_details)
    workers_ok = sum(worker["streams_ok"] for worker in worker_details)
    workers_error = sum(worker["streams_error"] for worker in worker_details)

    bandwidth_sent_mbps = 0.0
    bandwidth_recv_mbps = 0.0
    try:
        previous_raw = await redis_client.get(_LAST_NET_KEY)
        if previous_raw:
            previous = json.loads(previous_raw)
            dt = max(1.0, now.timestamp() - float(previous.get("timestamp", now.timestamp())))
            bandwidth_sent_mbps = max(0.0, (net.bytes_sent - int(previous.get("bytes_sent", net.bytes_sent))) / dt / 1e6)
            bandwidth_recv_mbps = max(0.0, (net.bytes_recv - int(previous.get("bytes_recv", net.bytes_recv))) / dt / 1e6)
        await redis_client.set(
            _LAST_NET_KEY,
            json.dumps({
                "timestamp": now.timestamp(),
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
            }),
            ex=settings.WORKER_STATUS_TTL,
        )
    except Exception as exc:
        logger.warning("Failed to update bandwidth baseline: %s", exc)

    payload = {
        "timestamp": now.isoformat(),
        "server": {
            "cpu_percent": cpu,
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total_gb": round(mem.total / 1e9, 2),
                "used_gb": round(mem.used / 1e9, 2),
                "available_gb": round(mem.available / 1e9, 2),
                "percent": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / 1e9, 2),
                "used_gb": round(disk.used / 1e9, 2),
                "free_gb": round(disk.free / 1e9, 2),
                "percent": disk.percent,
            },
            "network": {
                "bytes_sent_mb": round(net.bytes_sent / 1e6, 2),
                "bytes_recv_mb": round(net.bytes_recv / 1e6, 2),
                "bandwidth_sent_mbps": round(bandwidth_sent_mbps, 3),
                "bandwidth_recv_mbps": round(bandwidth_recv_mbps, 3),
            },
        },
        "workers": {
            "active_count": len(worker_details),
            "queue_depth": queue_depth,
            "assigned_total": workers_assigned,
            "ok_total": workers_ok,
            "error_total": workers_error,
            "details": worker_details,
        },
        "redis": {"connected": redis_ok},
    }
    return payload


async def _store_history_snapshot(payload: dict) -> None:
    snapshot = {
        "timestamp": payload["timestamp"],
        "cpu_percent": payload["server"]["cpu_percent"],
        "memory_percent": payload["server"]["memory"]["percent"],
        "disk_percent": payload["server"]["disk"]["percent"],
        "bandwidth_sent_mbps": payload["server"]["network"]["bandwidth_sent_mbps"],
        "bandwidth_recv_mbps": payload["server"]["network"]["bandwidth_recv_mbps"],
        "workers_active": payload["workers"]["active_count"],
        "workers_assigned": payload["workers"]["assigned_total"],
        "workers_ok": payload["workers"]["ok_total"],
        "workers_error": payload["workers"]["error_total"],
        "queue_depth": payload["workers"]["queue_depth"],
    }
    try:
        await redis_client.rpush(_HISTORY_KEY, json.dumps(snapshot))
        await redis_client.ltrim(_HISTORY_KEY, -_MAX_HISTORY_POINTS, -1)
        await redis_client.expire(_HISTORY_KEY, settings.WORKER_STATUS_TTL * 4)
    except Exception as exc:
        logger.warning("Failed to store metrics history snapshot: %s", exc)


@metrics_router.get("/metrics")
async def get_system_metrics(_u=Depends(get_current_user)):
    """Live server and worker stats. Auth required."""
    payload = await _build_metrics_payload()
    await _store_history_snapshot(payload)
    return payload


@metrics_router.get("/metrics/history")
async def get_system_metrics_history(
    minutes: int = Query(default=60, ge=5, le=1440),
    _u=Depends(get_current_user),
):
    """Historical system metrics snapshots for charts."""
    try:
        raw_points = await redis_client.lrange(_HISTORY_KEY, 0, -1)
    except Exception as exc:
        logger.warning("Failed to read metrics history from Redis: %s", exc)
        raw_points = []

    cutoff = datetime.now(timezone.utc).timestamp() - (minutes * 60)
    points = []
    for raw in raw_points:
        try:
            point = json.loads(raw)
            ts = datetime.fromisoformat(point["timestamp"]).timestamp()
            if ts >= cutoff:
                points.append(point)
        except Exception:
            continue

    if not points:
        current = await _build_metrics_payload()
        points = [{
            "timestamp": current["timestamp"],
            "cpu_percent": current["server"]["cpu_percent"],
            "memory_percent": current["server"]["memory"]["percent"],
            "disk_percent": current["server"]["disk"]["percent"],
            "bandwidth_sent_mbps": current["server"]["network"]["bandwidth_sent_mbps"],
            "bandwidth_recv_mbps": current["server"]["network"]["bandwidth_recv_mbps"],
            "workers_active": current["workers"]["active_count"],
            "workers_assigned": current["workers"]["assigned_total"],
            "workers_ok": current["workers"]["ok_total"],
            "workers_error": current["workers"]["error_total"],
            "queue_depth": current["workers"]["queue_depth"],
        }]

    return {
        "minutes": minutes,
        "points": points,
    }
