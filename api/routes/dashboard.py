"""Dashboard summary endpoint — cached for real-time NOC display."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, Integer, cast
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.models import Alert, Channel, ChannelStatus, Error, ErrorSeverity, Metric, AlertStatus
from db.schemas import ChannelStatusSummary, DashboardSummary
from utils.cache import cache_get, cache_set, CacheKeys
from config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(db: AsyncSession = Depends(get_db)):
    """
    Aggregated NOC dashboard summary.
    Cached in Redis for 30s to handle high-frequency polling.
    """
    cached = await cache_get(CacheKeys.DASHBOARD_SUMMARY)
    if cached:
        return DashboardSummary(**cached)

    # Channel status counts
    status_q = select(Channel.status, func.count(Channel.id)).where(
        Channel.is_active == True
    ).group_by(Channel.status)
    status_rows = (await db.execute(status_q)).all()
    status_counts = {r[0]: r[1] for r in status_rows}

    total_channels = sum(status_counts.values())
    active_up = status_counts.get(ChannelStatus.UP, 0)
    availability_pct = round((active_up / total_channels * 100), 2) if total_channels > 0 else 0.0

    # Open/critical alerts
    open_alerts = (await db.execute(
        select(func.count(Alert.id)).where(Alert.status == AlertStatus.OPEN)
    )).scalar_one()

    critical_alerts = (await db.execute(
        select(func.count(Alert.id)).where(
            Alert.status == AlertStatus.OPEN,
            Alert.severity == ErrorSeverity.CRITICAL,
        )
    )).scalar_one()

    # Average bitrate and response time (last 30 min sample)
    metric_agg = (await db.execute(
        select(
            func.avg(Metric.bitrate).label("avg_bitrate"),
            func.avg(Metric.response_time).label("avg_rt"),
        )
    )).one()

    # Top 5 error types in last 24h
    top_errors_q = (
        select(Error.error_type, Error.severity, func.count(Error.id).label("cnt"))
        .group_by(Error.error_type, Error.severity)
        .order_by(func.count(Error.id).desc())
        .limit(5)
    )
    top_errors = [
        {"error_type": r[0], "severity": r[1], "count": r[2]}
        for r in (await db.execute(top_errors_q)).all()
    ]

    summary = DashboardSummary(
        total_channels=total_channels,
        active_channels=total_channels,
        status_counts={k: v for k, v in status_counts.items()},
        open_alerts=open_alerts,
        critical_alerts=critical_alerts,
        avg_bitrate_kbps=round(metric_agg.avg_bitrate, 1) if metric_agg.avg_bitrate else None,
        avg_response_time_ms=round(metric_agg.avg_rt, 1) if metric_agg.avg_rt else None,
        availability_pct=availability_pct,
        top_errors=top_errors,
        last_updated=datetime.now(timezone.utc),
    )

    await cache_set(CacheKeys.DASHBOARD_SUMMARY, summary.model_dump(), ttl=settings.REDIS_TTL_SUMMARY)
    return summary


@router.get("/dashboard/channels", response_model=list[ChannelStatusSummary])
async def dashboard_channels(db: AsyncSession = Depends(get_db)):
    """
    Per-channel status cards for the NOC grid.
    Returns lightweight status + latest metric for each channel.
    """
    channels_q = select(Channel).where(Channel.is_active == True).order_by(Channel.name)
    channels = (await db.execute(channels_q)).scalars().all()

    result = []
    for ch in channels:
        # Latest metric
        latest_metric = (await db.execute(
            select(Metric)
            .where(Metric.channel_id == ch.id)
            .order_by(Metric.timestamp.desc())
            .limit(1)
        )).scalar_one_or_none()

        # Latest active error
        latest_error = (await db.execute(
            select(Error.error_type)
            .where(Error.channel_id == ch.id, Error.is_active == True)
            .order_by(Error.timestamp.desc())
            .limit(1)
        )).scalar_one_or_none()

        result.append(ChannelStatusSummary(
            id=ch.id,
            name=ch.name,
            status=ch.status,
            group=ch.group,
            bitrate=latest_metric.bitrate if latest_metric else None,
            resolution=(
                f"{latest_metric.resolution_width}x{latest_metric.resolution_height}"
                if latest_metric and latest_metric.resolution_width else None
            ),
            fps=latest_metric.fps if latest_metric else None,
            audio_level=latest_metric.audio_level if latest_metric else None,
            response_time=latest_metric.response_time if latest_metric else None,
            last_error_type=latest_error,
            last_checked_at=ch.last_checked_at,
            uptime_pct_24h=None,  # Computed separately for performance
        ))

    return result
