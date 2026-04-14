# -*- coding: utf-8 -*-
"""Dashboard summary endpoint."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.database import get_db
from db.models import Alert, AlertStatus, Channel, ChannelStatus, Error, ErrorSeverity, Metric
from db.schemas import AlertResponse, ChannelStatusSummary, DashboardSummary
from utils.cache import CacheKeys, cache_get, cache_set

router = APIRouter()


async def _build_worker_shard_map(db: AsyncSession) -> dict[str, int]:
    channel_ids = (
        await db.execute(select(Channel.id).order_by(Channel.created_at, Channel.id))
    ).scalars().all()
    total_workers = max(1, settings.TOTAL_WORKERS)
    return {str(channel_id): idx % total_workers for idx, channel_id in enumerate(channel_ids)}


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(db: AsyncSession = Depends(get_db)):
    cached = await cache_get(CacheKeys.DASHBOARD_SUMMARY)
    if cached:
        try:
            return DashboardSummary(**cached)
        except Exception:
            pass

    status_rows = (
        await db.execute(
            select(Channel.status, func.count(Channel.id))
            .where(Channel.is_active == True)
            .group_by(Channel.status)
        )
    ).all()
    status_counts = {r[0]: r[1] for r in status_rows}
    total_channels = sum(status_counts.values())
    active_up = status_counts.get(ChannelStatus.UP, 0)

    alert_rows = (
        await db.execute(select(Alert.status, Alert.severity, func.count(Alert.id)).group_by(Alert.status, Alert.severity))
    ).all()
    open_alerts = sum(count for status, _severity, count in alert_rows if status == AlertStatus.OPEN)
    critical_alerts = sum(
        count
        for status, severity, count in alert_rows
        if status == AlertStatus.OPEN and severity == ErrorSeverity.CRITICAL
    )
    warning_alerts = sum(
        count
        for status, severity, count in alert_rows
        if status == AlertStatus.OPEN and severity == ErrorSeverity.WARNING
    )
    acknowledged_alerts = sum(count for status, _severity, count in alert_rows if status == AlertStatus.ACKNOWLEDGED)

    metric_agg = (
        await db.execute(select(func.avg(Metric.bitrate).label("ab"), func.avg(Metric.response_time).label("ar")))
    ).one()

    top_errors = [
        {"error_type": r[0], "severity": r[1], "count": r[2]}
        for r in (
            await db.execute(
                select(Error.error_type, Error.severity, func.count(Error.id).label("cnt"))
                .group_by(Error.error_type, Error.severity)
                .order_by(func.count(Error.id).desc())
                .limit(5)
            )
        ).all()
    ]

    shard_map = await _build_worker_shard_map(db)
    recent_rows = (
        await db.execute(
            select(Alert, Channel)
            .join(Channel, Channel.id == Alert.channel_id)
            .order_by(Alert.triggered_at.desc())
            .limit(6)
        )
    ).all()
    recent_alerts = [
        AlertResponse(
            id=alert.id,
            channel_id=alert.channel_id,
            channel_name=channel_row.name,
            channel_group=channel_row.group,
            channel_status=channel_row.status,
            alert_type=alert.alert_type,
            severity=alert.severity,
            status=alert.status,
            message=alert.message,
            triggered_at=alert.triggered_at,
            acknowledged_at=alert.acknowledged_at,
            acknowledged_by=alert.acknowledged_by,
            resolved_at=alert.resolved_at,
            notification_sent=alert.notification_sent,
            worker_shard=shard_map.get(str(alert.channel_id)),
            worker_label=f"Worker {shard_map.get(str(alert.channel_id), 0):02d}",
        )
        for alert, channel_row in recent_rows
    ]

    summary = DashboardSummary(
        total_channels=total_channels,
        active_channels=total_channels,
        status_counts={k: v for k, v in status_counts.items()},
        open_alerts=open_alerts,
        critical_alerts=critical_alerts,
        warning_alerts=warning_alerts,
        acknowledged_alerts=acknowledged_alerts,
        avg_bitrate_kbps=round(metric_agg.ab, 1) if metric_agg.ab else None,
        avg_response_time_ms=round(metric_agg.ar, 1) if metric_agg.ar else None,
        availability_pct=round((active_up / total_channels * 100), 2) if total_channels > 0 else 0.0,
        top_errors=top_errors,
        recent_alerts=recent_alerts,
        last_updated=datetime.now(timezone.utc),
    )
    await cache_set(CacheKeys.DASHBOARD_SUMMARY, summary.model_dump(), ttl=settings.REDIS_TTL_SUMMARY)
    return summary


@router.get("/dashboard/channels", response_model=list[ChannelStatusSummary])
async def dashboard_channels(db: AsyncSession = Depends(get_db)):
    channels = (await db.execute(select(Channel).where(Channel.is_active == True).order_by(Channel.name))).scalars().all()
    result = []
    for ch in channels:
        lm = (
            await db.execute(
                select(Metric).where(Metric.channel_id == ch.id).order_by(Metric.timestamp.desc()).limit(1)
            )
        ).scalar_one_or_none()
        le = (
            await db.execute(
                select(Error.error_type)
                .where(Error.channel_id == ch.id, Error.is_active == True)
                .order_by(Error.timestamp.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        result.append(
            ChannelStatusSummary(
                id=ch.id,
                name=ch.name,
                status=ch.status,
                group=ch.group,
                bitrate=lm.bitrate if lm else None,
                resolution=(f"{lm.resolution_width}x{lm.resolution_height}" if lm and lm.resolution_width else None),
                fps=lm.fps if lm else None,
                audio_level=lm.audio_level if lm else None,
                response_time=lm.response_time if lm else None,
                last_error_type=le,
                last_checked_at=ch.last_checked_at,
                uptime_pct_24h=None,
            )
        )
    return result
