# -*- coding: utf-8 -*-
"""
api/logs/logs_routes.py  (v2.2)
Application log viewer endpoints.
  GET  /api/v1/logs                 - query logs with filters
  GET  /api/v1/logs/stats           - counts by level for last 24h
  DELETE /api/v1/logs/purge         - purge logs older than N days
  POST /api/v1/logs/{id}/email      - email a specific log entry
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.auth_deps import get_current_user, require_admin
from db.database import get_db

router = APIRouter(prefix="/api/v1/logs", tags=["Logs"])

LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


# ---- schemas -----------------------------------------------------------------

class LogEntry(BaseModel):
    id:        int
    timestamp: str
    level:     str
    logger:    str
    message:   str
    exception: Optional[str] = None
    source:    Optional[str] = None

    model_config = {"from_attributes": True}


class LogStats(BaseModel):
    debug:    int = 0
    info:     int = 0
    warning:  int = 0
    error:    int = 0
    critical: int = 0
    total:    int = 0
    period:   str = "24h"


class EmailLogRequest(BaseModel):
    to_email: str


# ---- helpers -----------------------------------------------------------------

def _v(row, key: str, default=""):
    v = getattr(row, key, default)
    return str(v) if v is not None else default


# ---- endpoints ---------------------------------------------------------------

@router.get("", response_model=dict)
async def query_logs(
    level:  Optional[str] = Query(None, description="DEBUG|INFO|WARNING|ERROR|CRITICAL"),
    logger: Optional[str] = Query(None, description="Logger name contains"),
    search: Optional[str] = Query(None, description="Message contains"),
    since:  Optional[str] = Query(None, description="ISO datetime, e.g. 2024-01-01T00:00:00"),
    until:  Optional[str] = Query(None, description="ISO datetime"),
    limit:  int            = Query(200, ge=1, le=2000),
    offset: int            = Query(0,   ge=0),
    db: AsyncSession = Depends(get_db),
    _u = Depends(get_current_user),
):
    """Query application logs with optional filters."""
    from db.models import AppLog
    q = select(AppLog).order_by(AppLog.timestamp.desc())

    if level and level.upper() in LEVELS:
        q = q.where(AppLog.level == level.upper())
    if logger:
        q = q.where(AppLog.logger.ilike(f"%{logger}%"))
    if search:
        q = q.where(AppLog.message.ilike(f"%{search}%"))
    if since:
        try:
            dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            q  = q.where(AppLog.timestamp >= dt)
        except ValueError:
            pass
    if until:
        try:
            dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
            q  = q.where(AppLog.timestamp <= dt)
        except ValueError:
            pass

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total   = (await db.execute(count_q)).scalar_one()

    # Page
    q    = q.offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    return {
        "total":  total,
        "offset": offset,
        "limit":  limit,
        "items":  [
            {
                "id":        r.id,
                "timestamp": _v(r, "timestamp"),
                "level":     _v(r, "level"),
                "logger":    _v(r, "logger"),
                "message":   _v(r, "message"),
                "exception": _v(r, "exception") or None,
                "source":    _v(r, "source") or None,
            }
            for r in rows
        ],
    }


@router.get("/stats", response_model=LogStats)
async def log_stats(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    _u = Depends(get_current_user),
):
    """Count log entries by level for the last N hours."""
    from db.models import AppLog
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    rows = (await db.execute(
        select(AppLog.level, func.count(AppLog.id).label("cnt"))
        .where(AppLog.timestamp >= since)
        .group_by(AppLog.level)
    )).all()

    counts: dict = {}
    for row in rows:
        counts[row[0].lower()] = row[1]

    total = sum(counts.values())
    return LogStats(
        debug=counts.get("debug",    0),
        info=counts.get("info",      0),
        warning=counts.get("warning",0),
        error=counts.get("error",    0),
        critical=counts.get("critical",0),
        total=total,
        period=f"{hours}h",
    )


@router.delete("/purge")
async def purge_logs(
    days: int = Query(30, ge=1, le=365, description="Delete logs older than N days"),
    db: AsyncSession = Depends(get_db),
    _a = Depends(require_admin),
):
    """Delete log entries older than N days. Admin only."""
    from db.models import AppLog
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        delete(AppLog).where(AppLog.timestamp < cutoff)
    )
    deleted = result.rowcount
    await db.commit()
    return {"deleted": deleted, "older_than_days": days}


@router.post("/{log_id}/email")
async def email_log_entry(
    log_id: int,
    req: EmailLogRequest,
    db: AsyncSession = Depends(get_db),
    _u = Depends(get_current_user),
):
    """Send a specific log entry to an email address via configured SMTP."""
    from db.models import AppLog
    from utils.smtp_helper import resolve_smtp_config, send_email_sync

    row = (await db.execute(
        select(AppLog).where(AppLog.id == log_id)
    )).scalar_one_or_none()

    if not row:
        raise HTTPException(404, "Log entry not found")

    cfg = await resolve_smtp_config()
    if not cfg:
        raise HTTPException(400, "SMTP not configured. Configure it in Settings > SMTP.")

    ts  = _v(row, "timestamp")
    lvl = _v(row, "level")
    lg  = _v(row, "logger")
    msg = _v(row, "message")
    exc = _v(row, "exception")

    level_colors = {
        "CRITICAL": "#dc2626",
        "ERROR":    "#dc2626",
        "WARNING":  "#d97706",
        "INFO":     "#2563eb",
        "DEBUG":    "#6b7280",
    }
    color = level_colors.get(lvl, "#374151")

    body_html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;max-width:700px">
<h2 style="color:#1E3A5F">OTT Monitor - Log Entry #{log_id}</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
  <tr style="background:#1E3A5F;color:#fff"><th>Field</th><th>Value</th></tr>
  <tr><td><b>Timestamp</b></td><td>{ts}</td></tr>
  <tr><td><b>Level</b></td>
    <td style="color:{color};font-weight:bold">{lvl}</td></tr>
  <tr><td><b>Logger</b></td><td style="font-family:monospace">{lg}</td></tr>
  <tr><td><b>Message</b></td><td>{msg}</td></tr>
  {'<tr><td><b>Exception</b></td><td style="font-family:monospace;white-space:pre-wrap;font-size:11px">' + exc + '</td></tr>' if exc else ''}
</table>
<p style="margin-top:20px;font-size:11px;color:#999">Sent from OTT Monitor NOC Dashboard</p>
</body></html>"""

    ok = await asyncio.to_thread(
        send_email_sync, cfg, [req.to_email],
        f"[OTT Monitor] Log Entry #{log_id}: [{lvl}] {lg}",
        body_html
    )
    if not ok:
        raise HTTPException(500, "Failed to send email. Check SMTP configuration.")

    return {"message": f"Log entry #{log_id} sent to {req.to_email}"}
