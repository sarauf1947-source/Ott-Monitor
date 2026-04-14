# -*- coding: utf-8 -*-
"""Alerts CRUD endpoints."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.database import get_db
from db.models import Alert, AlertStatus, Channel, ErrorSeverity
from db.schemas import AlertAcknowledge, AlertListResponse, AlertResponse, AlertSummary

router = APIRouter()


async def _build_worker_shard_map(db: AsyncSession) -> dict[str, int]:
    channel_ids = (
        await db.execute(select(Channel.id).order_by(Channel.created_at, Channel.id))
    ).scalars().all()
    total_workers = max(1, settings.TOTAL_WORKERS)
    return {str(channel_id): idx % total_workers for idx, channel_id in enumerate(channel_ids)}


def _worker_label(worker_shard: int | None) -> Optional[str]:
    if worker_shard is None:
        return None
    return f"Worker {worker_shard:02d}"


@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    status: Optional[AlertStatus] = None,
    severity: Optional[ErrorSeverity] = None,
    channel_id: Optional[uuid.UUID] = None,
    channel: Optional[str] = None,
    search: Optional[str] = None,
    worker_shard: Optional[int] = Query(default=None, ge=0),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    include_info: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    shard_map = await _build_worker_shard_map(db)

    base_query = select(Alert, Channel).join(Channel, Channel.id == Alert.channel_id)

    if status:
        base_query = base_query.where(Alert.status == status)
    if severity:
        base_query = base_query.where(Alert.severity == severity)
    if channel_id:
        base_query = base_query.where(Alert.channel_id == channel_id)
    if channel:
        base_query = base_query.where(Channel.name.ilike(f"%{channel.strip()}%"))
    if search:
        term = f"%{search.strip()}%"
        base_query = base_query.where(
            or_(
                Alert.message.ilike(term),
                cast(Alert.alert_type, String).ilike(term),
                Channel.name.ilike(term),
                Channel.group.ilike(term),
            )
        )
    if date_from:
        base_query = base_query.where(Alert.triggered_at >= date_from)
    if date_to:
        base_query = base_query.where(Alert.triggered_at <= date_to)
    if not include_info:
        base_query = base_query.where(Alert.severity != ErrorSeverity.INFO)

    rows = (await db.execute(base_query.order_by(Alert.triggered_at.desc()))).all()

    filtered_rows = []
    for alert, channel_row in rows:
        shard_id = shard_map.get(str(alert.channel_id))
        if worker_shard is not None and shard_id != worker_shard:
            continue
        filtered_rows.append((alert, channel_row, shard_id))

    total = len(filtered_rows)
    window = filtered_rows[offset:offset + limit]

    summary = AlertSummary(
        total=total,
        open=sum(1 for alert, _, _ in filtered_rows if alert.status == AlertStatus.OPEN),
        acknowledged=sum(1 for alert, _, _ in filtered_rows if alert.status == AlertStatus.ACKNOWLEDGED),
        resolved=sum(1 for alert, _, _ in filtered_rows if alert.status == AlertStatus.RESOLVED),
        critical=sum(1 for alert, _, _ in filtered_rows if alert.severity == ErrorSeverity.CRITICAL),
        major=sum(1 for alert, _, _ in filtered_rows if alert.severity == ErrorSeverity.MAJOR),
        warning=sum(1 for alert, _, _ in filtered_rows if alert.severity == ErrorSeverity.WARNING),
        info=sum(1 for alert, _, _ in filtered_rows if alert.severity == ErrorSeverity.INFO),
    )

    items = [
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
            worker_shard=shard_id,
            worker_label=_worker_label(shard_id),
        )
        for alert, channel_row, shard_id in window
    ]

    return AlertListResponse(
        total=total,
        limit=limit,
        offset=offset,
        summary=summary,
        items=items,
    )


@router.patch("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: uuid.UUID, payload: AlertAcknowledge, db: AsyncSession = Depends(get_db)):
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    channel_row = (await db.execute(select(Channel).where(Channel.id == alert.channel_id))).scalar_one()
    shard_map = await _build_worker_shard_map(db)
    shard_id = shard_map.get(str(alert.channel_id))
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = payload.acknowledged_by
    await db.flush()
    return AlertResponse(
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
        worker_shard=shard_id,
        worker_label=_worker_label(shard_id),
    )


@router.patch("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    channel_row = (await db.execute(select(Channel).where(Channel.id == alert.channel_id))).scalar_one()
    shard_map = await _build_worker_shard_map(db)
    shard_id = shard_map.get(str(alert.channel_id))
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return AlertResponse(
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
        worker_shard=shard_id,
        worker_label=_worker_label(shard_id),
    )
