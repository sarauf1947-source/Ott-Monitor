# -*- coding: utf-8 -*-
"""
api/main.py  (v2.2 - complete)
OTT Monitor FastAPI application.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

# Original routes
from api.routes import channels, dashboard, metrics, errors, alerts, reports, health
# v2.0 routes
from api.auth import auth_router, users_router
from api.auth.auth_utils import hash_password
from api.settings.settings_routes import settings_router
from api.settings.dashboard_routes import dashboard_router
from api.system_metrics.metrics_routes import metrics_router
from api.reporting.reporting_routes import reporting_router
from api.reporting.scheduler import setup_scheduler
from api.reporting.scheduler import scheduler as _apscheduler
# v2.2 routes
from api.logs import logs_router

from db.database import engine, Base, create_hypertables, AsyncSessionLocal
from utils.logger import setup_logging
from utils.cache import redis_client
from config import settings

setup_logging()
logger = logging.getLogger(__name__)


async def _seed_admin() -> None:
    from db.models import User
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(User).limit(1))
            if result.scalar_one_or_none() is None:
                db.add(User(
                    username="admin",
                    email="admin@ottmonitor.local",
                    full_name="System Administrator",
                    hashed_password=hash_password("Admin@12345"),
                    role="admin",
                    is_active=True,
                ))
                await db.commit()
                logger.warning(
                    "Default admin created -- username=admin password=Admin@12345"
                    " -- CHANGE THIS PASSWORD IMMEDIATELY"
                )
        except Exception as exc:
            await db.rollback()
            logger.warning(f"Admin seed skipped: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OTT Monitor API v2.2...")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized")
        try:
            await create_hypertables()
        except Exception as exc:
            logger.warning(f"TimescaleDB hypertable setup skipped: {exc}")
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")
        raise

    try:
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as exc:
        logger.warning(f"Redis not available: {exc}")

    await _seed_admin()

    try:
        from utils.db_log_handler import install_db_handler
        install_db_handler(min_level=logging.WARNING)
        logger.info("DB log handler installed")
    except Exception as exc:
        logger.warning(f"DB log handler skipped: {exc}")

    try:
        setup_scheduler(AsyncSessionLocal)
        logger.info("Report scheduler started")
    except Exception as exc:
        logger.warning(f"Scheduler start failed (non-fatal): {exc}")

    logger.info("OTT Monitor API ready - v2.2")
    yield

    logger.info("Shutting down OTT Monitor API...")
    try:
        if _apscheduler.running:
            _apscheduler.shutdown(wait=False)
    except Exception:
        pass
    await engine.dispose()
    await redis_client.aclose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="OTT/IPTV Monitor API",
    description="Production-grade monitoring platform for HLS/DASH live streams.",
    version="2.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.perf_counter() - start:.4f}s"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"{request.method} {request.url.path}")
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception(f"Unhandled error: {request.method} {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc)},
        )


API_PREFIX = "/api/v1"

# Original routes
app.include_router(health.router,    prefix=API_PREFIX, tags=["Health"])
app.include_router(channels.router,  prefix=API_PREFIX, tags=["Channels"])
app.include_router(metrics.router,   prefix=API_PREFIX, tags=["Metrics"])
app.include_router(errors.router,    prefix=API_PREFIX, tags=["Errors"])
app.include_router(dashboard.router, prefix=API_PREFIX, tags=["Dashboard"])
app.include_router(alerts.router,    prefix=API_PREFIX, tags=["Alerts"])
app.include_router(reports.router,   prefix=API_PREFIX, tags=["Reports"])

# v2.0 routes (own prefix)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(dashboard_router)
app.include_router(metrics_router)
app.include_router(reporting_router)

# v2.2 routes
app.include_router(logs_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "OTT/IPTV Monitor API",
        "version": "2.2.0",
        "docs":    "/api/docs",
        "health":  "/api/v1/health",
    }
