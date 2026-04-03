"""Alerts CRUD endpoints."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from db.database import get_db
from db.models import Alert, AlertStatus, ErrorSeverity
from db.schemas import AlertAcknowledge, AlertListResponse, AlertResponse

router = APIRouter()


@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    status: Optional[AlertStatus] = None,
    severity: Optional[ErrorSeverity] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = select(Alert).order_by(Alert.triggered_at.desc()).limit(limit)
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    rows = (await db.execute(query)).scalars().all()
    return AlertListResponse(total=len(rows), items=[AlertResponse.model_validate(r) for r in rows])


@router.patch("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    payload: AlertAcknowledge,
    db: AsyncSession = Depends(get_db),
):
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = payload.acknowledged_by
    await db.flush()
    return AlertResponse.model_validate(alert)


@router.patch("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return AlertResponse.model_validate(alert)
