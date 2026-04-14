# -*- coding: utf-8 -*-
"""Errors endpoint."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.models import Error, ErrorSeverity, ErrorType
from db.schemas import ErrorListResponse, ErrorResponse

router = APIRouter()

@router.get("/channels/{channel_id}/errors", response_model=ErrorListResponse)
async def get_channel_errors(channel_id: uuid.UUID, hours: int = Query(24, ge=1, le=720), severity: Optional[ErrorSeverity] = None, error_type: Optional[ErrorType] = None, active_only: bool = False, limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = select(Error).where(Error.channel_id == channel_id, Error.timestamp >= since).order_by(Error.timestamp.desc()).limit(limit)
    if severity:    query = query.where(Error.severity == severity)
    if error_type:  query = query.where(Error.error_type == error_type)
    if active_only: query = query.where(Error.is_active == True)
    rows = (await db.execute(query)).scalars().all()
    return ErrorListResponse(channel_id=channel_id, total=len(rows), items=[ErrorResponse.model_validate(r) for r in rows])
