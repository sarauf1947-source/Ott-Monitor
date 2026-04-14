# -*- coding: utf-8 -*-
"""Metrics endpoints."""
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, cast, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.models import Metric
from db.schemas import MetricListResponse, MetricResponse, MetricSummary

router = APIRouter()

@router.get("/channels/{channel_id}/metrics", response_model=MetricListResponse)
async def get_channel_metrics(channel_id: uuid.UUID, hours: int = Query(24, ge=1, le=720), limit: int = Query(200, ge=1, le=1000), db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (await db.execute(select(Metric).where(Metric.channel_id == channel_id, Metric.timestamp >= since).order_by(Metric.timestamp.desc()).limit(limit))).scalars().all()
    return MetricListResponse(channel_id=channel_id, total=len(rows), items=[MetricResponse.model_validate(r) for r in rows])

@router.get("/channels/{channel_id}/metrics/summary", response_model=MetricSummary)
async def get_metric_summary(channel_id: uuid.UUID, hours: int = Query(24, ge=1, le=720), db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    row = (await db.execute(select(func.avg(Metric.bitrate).label("ab"), func.min(Metric.bitrate).label("mn"), func.max(Metric.bitrate).label("mx"), func.avg(Metric.response_time).label("ar"), func.count(Metric.id).label("tot"), func.sum(cast(Metric.is_available, Integer)).label("av")).where(Metric.channel_id == channel_id, Metric.timestamp >= since))).one()
    total = row.tot or 0; avail = row.av or 0
    return MetricSummary(channel_id=channel_id, period=f"{hours}h", avg_bitrate=round(row.ab, 1) if row.ab else None, min_bitrate=row.mn, max_bitrate=row.mx, avg_response_time=round(row.ar, 1) if row.ar else None, availability_pct=round((avail / total * 100), 2) if total > 0 else 0.0, sample_count=total)
