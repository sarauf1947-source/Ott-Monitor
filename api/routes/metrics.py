"""Metrics endpoint."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, Integer, cast
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.models import Metric
from db.schemas import MetricListResponse, MetricResponse, MetricSummary
from utils.cache import CacheKeys, cache_get, cache_set
from config import settings

router = APIRouter()


@router.get("/channels/{channel_id}/metrics", response_model=MetricListResponse)
async def get_channel_metrics(
    channel_id: uuid.UUID,
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(Metric)
        .where(Metric.channel_id == channel_id, Metric.timestamp >= since)
        .order_by(Metric.timestamp.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return MetricListResponse(
        channel_id=channel_id,
        total=len(rows),
        items=[MetricResponse.model_validate(r) for r in rows],
    )


@router.get("/channels/{channel_id}/metrics/summary", response_model=MetricSummary)
async def get_metric_summary(
    channel_id: uuid.UUID,
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(
            func.avg(Metric.bitrate).label("avg_bitrate"),
            func.min(Metric.bitrate).label("min_bitrate"),
            func.max(Metric.bitrate).label("max_bitrate"),
            func.avg(Metric.response_time).label("avg_response_time"),
            func.count(Metric.id).label("total"),
            func.sum(cast(Metric.is_available, Integer)).label("available"),
        ).where(Metric.channel_id == channel_id, Metric.timestamp >= since)
    )
    row = result.one()

    total = row.total or 0
    available = row.available or 0
    avail_pct = round((available / total * 100), 2) if total > 0 else 0.0

    return MetricSummary(
        channel_id=channel_id,
        period=f"{hours}h",
        avg_bitrate=round(row.avg_bitrate, 1) if row.avg_bitrate else None,
        min_bitrate=row.min_bitrate,
        max_bitrate=row.max_bitrate,
        avg_response_time=round(row.avg_response_time, 1) if row.avg_response_time else None,
        availability_pct=avail_pct,
        sample_count=total,
    )
