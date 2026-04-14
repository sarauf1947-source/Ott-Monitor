# -*- coding: utf-8 -*-
"""Health check endpoint."""
import time
from fastapi import APIRouter
from db.schemas import HealthResponse
from utils.cache import redis_client
from db.database import AsyncSessionLocal
from sqlalchemy import text

router = APIRouter()
_START_TIME = time.time()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    db_status = "ok"
    redis_status = "ok"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    try:
        await redis_client.ping()
    except Exception:
        redis_status = "error"
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        redis=redis_status,
        version="2.3.0",
        uptime_seconds=round(time.time() - _START_TIME, 1),
    )
