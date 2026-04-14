# -*- coding: utf-8 -*-
"""
api/routes/reports.py
Fixes:
  - is_available cast now uses sqlalchemy.cast(Metric.is_available, Integer)
  - Added predefined report templates
  - Added XLSX export endpoint
  - Kept original generate + csv endpoints intact
"""
import csv
import io
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, cast, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Channel, Error, Metric
from db.schemas import ReportRequest, ReportResponse

router = APIRouter()


# -- Helper: core aggregation query --------------------------------------------

async def _aggregate_channel(db: AsyncSession, ch: Channel,
                              start: datetime, end: datetime) -> dict:
    """Aggregate metrics and errors for one channel over a time window."""
    # Metrics aggregation - cast is_available to Integer for SUM
    agg = (await db.execute(
        select(
            func.avg(Metric.bitrate).label("avg_bitrate"),
            func.count(Metric.id).label("total"),
            func.sum(cast(Metric.is_available, Integer)).label("available"),
            func.avg(Metric.response_time).label("avg_rt"),
        ).where(
            Metric.channel_id == ch.id,
            Metric.timestamp >= start,
            Metric.timestamp <= end,
        )
    )).one()

    total     = agg.total or 0
    available = int(agg.available or 0)

    entry: dict = {
        "channel_id":          str(ch.id),
        "channel_name":        ch.name,
        "group":               ch.group,
        "status":              ch.status.value if hasattr(ch.status, "value") else str(ch.status),
        "avg_bitrate_kbps":    round(agg.avg_bitrate, 1) if agg.avg_bitrate else None,
        "avg_response_time_ms": round(agg.avg_rt, 1) if agg.avg_rt else None,
        "availability_pct":    round(available / total * 100, 2) if total > 0 else 0.0,
        "metric_samples":      total,
    }

    # Error breakdown
    error_rows = (await db.execute(
        select(Error.error_type, func.count(Error.id).label("cnt"))
        .where(
            Error.channel_id == ch.id,
            Error.timestamp >= start,
            Error.timestamp <= end,
        )
        .group_by(Error.error_type)
        .order_by(func.count(Error.id).desc())
    )).all()

    def _v(v):
        return v.value if hasattr(v, "value") else str(v)

    entry["errors"]       = {_v(r[0]): r[1] for r in error_rows}
    entry["total_errors"] = sum(r[1] for r in error_rows)
    return entry


# -- Original endpoints (preserved) --------------------------------------------

@router.post("/reports/generate", response_model=ReportResponse)
async def generate_report(payload: ReportRequest, db: AsyncSession = Depends(get_db)):
    """Generate a JSON summary report for the requested channels and time range."""
    channel_q = select(Channel).where(Channel.is_active == True)  # noqa: E712
    if payload.channel_ids:
        channel_q = channel_q.where(Channel.id.in_(payload.channel_ids))
    channels = (await db.execute(channel_q)).scalars().all()

    report_data = []
    for ch in channels:
        entry: dict = {"channel_id": str(ch.id), "channel_name": ch.name, "group": ch.group}

        if payload.include_metrics:
            agg = (await db.execute(
                select(
                    func.avg(Metric.bitrate).label("avg_bitrate"),
                    func.count(Metric.id).label("total"),
                    func.sum(cast(Metric.is_available, Integer)).label("available"),
                    func.avg(Metric.response_time).label("avg_rt"),
                ).where(
                    Metric.channel_id == ch.id,
                    Metric.timestamp >= payload.start_time,
                    Metric.timestamp <= payload.end_time,
                )
            )).one()

            total     = agg.total or 0
            available = int(agg.available or 0)
            entry["avg_bitrate_kbps"]    = round(agg.avg_bitrate, 1) if agg.avg_bitrate else None
            entry["avg_response_time_ms"] = round(agg.avg_rt, 1) if agg.avg_rt else None
            entry["availability_pct"]    = round(available / total * 100, 2) if total > 0 else 0
            entry["metric_samples"]      = total

        if payload.include_errors:
            error_counts = (await db.execute(
                select(Error.error_type, func.count(Error.id).label("cnt"))
                .where(
                    Error.channel_id == ch.id,
                    Error.timestamp >= payload.start_time,
                    Error.timestamp <= payload.end_time,
                )
                .group_by(Error.error_type)
            )).all()
            entry["errors"]       = {r[0]: r[1] for r in error_counts}
            entry["total_errors"] = sum(r[1] for r in error_counts)

        report_data.append(entry)

    return ReportResponse(
        report_id=str(uuid.uuid4()),
        generated_at=datetime.now(timezone.utc),
        period_start=payload.start_time,
        period_end=payload.end_time,
        channel_count=len(channels),
        data=report_data,
    )


@router.post("/reports/export/csv")
async def export_csv(payload: ReportRequest, db: AsyncSession = Depends(get_db)):
    """Export report as CSV file download."""
    report = await generate_report(payload, db)

    output = io.StringIO()
    if report.data:
        writer = csv.DictWriter(output, fieldnames=report.data[0].keys())
        writer.writeheader()
        for row in report.data:
            flat = {k: (str(v) if isinstance(v, dict) else v) for k, v in row.items()}
            writer.writerow(flat)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=ott_report_{report.report_id[:8]}.csv"
        },
    )


# -- NEW: Predefined report templates ------------------------------------------

@router.get("/reports/predefined/uptime")
async def report_uptime(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Uptime/downtime summary for all active channels over N days."""
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    channels = (await db.execute(
        select(Channel).where(Channel.is_active == True)  # noqa: E712
    )).scalars().all()

    rows = []
    for ch in channels:
        e = await _aggregate_channel(db, ch, start, end)
        rows.append({
            "channel":          e["channel_name"],
            "group":            e["group"] or "-",
            "status":           e["status"],
            "uptime_pct":       e["availability_pct"],
            "total_checks":     e["metric_samples"],
            "total_errors":     e["total_errors"],
        })

    rows.sort(key=lambda r: r["uptime_pct"])
    return {
        "report_type": "uptime",
        "period_days": days,
        "generated_at": end.isoformat(),
        "channel_count": len(rows),
        "data": rows,
    }


@router.get("/reports/predefined/errors")
async def report_errors(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Top error breakdown for all channels over N days."""
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    error_rows = (await db.execute(
        select(
            Error.error_type,
            Error.severity,
            func.count(Error.id).label("count"),
        )
        .where(Error.timestamp >= start)
        .group_by(Error.error_type, Error.severity)
        .order_by(func.count(Error.id).desc())
        .limit(50)
    )).all()

    def _v(v):
        return v.value if hasattr(v, "value") else str(v)

    return {
        "report_type": "errors",
        "period_days": days,
        "generated_at": end.isoformat(),
        "data": [
            {"error_type": _v(r[0]), "severity": _v(r[1]), "count": r[2]}
            for r in error_rows
        ],
    }


@router.get("/reports/predefined/bitrate")
async def report_bitrate(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Average bitrate trends for all channels over N days."""
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    channels = (await db.execute(
        select(Channel).where(Channel.is_active == True)  # noqa: E712
    )).scalars().all()

    rows = []
    for ch in channels:
        e = await _aggregate_channel(db, ch, start, end)
        rows.append({
            "channel":        e["channel_name"],
            "group":          e["group"] or "-",
            "avg_bitrate":    e["avg_bitrate_kbps"],
            "expected":       ch.expected_bitrate,
            "avg_latency_ms": e["avg_response_time_ms"],
        })

    rows.sort(key=lambda r: (r["avg_bitrate"] or 0), reverse=True)
    return {
        "report_type": "bitrate",
        "period_days": days,
        "generated_at": end.isoformat(),
        "channel_count": len(rows),
        "data": rows,
    }


# -- NEW: XLSX export -----------------------------------------------------------

@router.post("/reports/export/xlsx")
async def export_xlsx(payload: ReportRequest, db: AsyncSession = Depends(get_db)):
    """Export report as XLSX file (Excel-compatible)."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        from fastapi import HTTPException
        raise HTTPException(500, "openpyxl not installed")

    report = await generate_report(payload, db)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "OTT Report"

    hdr_font = Font(bold=True, color="FFFFFF")
    hdr_fill = PatternFill(fill_type="solid", fgColor="1E3A5F")

    ws["A1"] = "OTT Monitor - Channel Report"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = f"Period: {payload.start_time.isoformat()} to {payload.end_time.isoformat()}"
    ws["A3"] = f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

    if report.data:
        headers = list(report.data[0].keys())
        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=5, column=c, value=h.replace("_", " ").title())
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center")

        for r, row in enumerate(report.data, 6):
            for c, key in enumerate(headers, 1):
                v = row.get(key)
                ws.cell(row=r, column=c, value=str(v) if isinstance(v, dict) else v)

        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max((len(str(c.value or "")) for c in col), default=8) + 3, 40
            )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"ott_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


# -- NEW: Stream connectivity diagnostic ---------------------------------------

@router.get("/reports/stream-check")
async def stream_connectivity_check(
    url: str = Query(..., description="Stream URL to test"),
):
    """
    Diagnose why a stream URL might not be reachable from the monitoring workers.
    Returns diagnostic information - does NOT actually probe the stream.
    """
    reasons = []
    suggestions = []

    url_lower = url.lower()

    # Check 1: localhost/127.0.0.1 from inside Docker
    if "localhost" in url_lower or "127.0.0.1" in url_lower:
        reasons.append(
            "URL uses 'localhost' or '127.0.0.1'. "
            "Inside Docker containers, 'localhost' refers to the container itself, "
            "not the host machine."
        )
        suggestions.append(
            "Use your server's actual LAN IP (e.g. 192.168.x.x) or "
            "host.docker.internal instead of localhost."
        )

    # Check 2: SIMULATE_MODE
    reasons.append(
        "If SIMULATE_MODE=true in your .env file, ffprobe is never called. "
        "The worker returns simulated data regardless of the URL."
    )
    suggestions.append(
        "Set SIMULATE_MODE=false in /opt/ott_monitor/.env and restart workers: "
        "docker compose -f deployment/docker-compose.yml restart"
    )

    # Check 3: Private IP ranges
    import re
    private = re.compile(
        r"(^10\.)|(^172\.(1[6-9]|2[0-9]|3[01])\.)|(^192\.168\.)"
    )
    host_match = re.search(r"https?://([^/:]+)", url_lower)
    if host_match:
        host = host_match.group(1)
        if private.match(host):
            reasons.append(
                f"URL uses a private IP ({host}). This is reachable from Docker "
                "only if the stream server is on the same Docker network or the "
                "host network mode is used."
            )
            suggestions.append(
                "Ensure the stream server is accessible from within the Docker network. "
                "Test with: docker compose exec worker curl -I " + url
            )

    # Check 4: Protocol
    if url_lower.startswith("rtsp://") or url_lower.startswith("rtmp://"):
        reasons.append(
            "RTSP/RTMP streams require ffprobe with network support. "
            "Ensure the worker container has full ffmpeg installed (not just ffprobe)."
        )
        suggestions.append(
            "The worker Dockerfile installs full ffmpeg which includes RTSP/RTMP support. "
            "Verify with: docker compose exec worker ffprobe -version"
        )

    # Check 5: HTTP vs HTTPS
    if url_lower.startswith("http://"):
        suggestions.append(
            "HTTP streams work fine. If using HTTPS with a self-signed certificate, "
            "add -tls_verify 0 to ffprobe args in workers/stream_analyzer.py"
        )

    return {
        "url":         url,
        "checked_at":  datetime.now(timezone.utc).isoformat(),
        "reasons_stream_may_fail": reasons,
        "suggestions": suggestions,
        "manual_test": (
            f"docker compose -f deployment/docker-compose.yml "
            f"exec worker ffprobe -v quiet -print_format json "
            f"-show_streams '{url}'"
        ),
        "simulate_mode_check": (
            "grep SIMULATE_MODE /opt/ott_monitor/.env"
        ),
    }
