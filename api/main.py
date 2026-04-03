"""
OTT/IPTV Monitor - Main FastAPI Application
Production-grade API server for monitoring 300-350 HLS/DASH live streams
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from api.routes import channels, dashboard, metrics, errors, alerts, reports, health
from db.database import engine, Base, create_hypertables
from utils.logger import setup_logging
from utils.cache import redis_client
from config import settings

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("Starting OTT Monitor API...")
    try:
        # Create all DB tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized")
        # Try to set up TimescaleDB hypertables (no-op on plain PostgreSQL)
        try:
            await create_hypertables()
        except Exception as e:
            logger.warning(f"TimescaleDB hypertable setup skipped: {e}")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    try:
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis not available: {e} — running without cache")

    logger.info("OTT Monitor API ready")
    yield

    # Shutdown
    logger.info("Shutting down OTT Monitor API...")
    await engine.dispose()
    await redis_client.aclose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="OTT/IPTV Monitor API",
    description=(
        "Production-grade monitoring platform for HLS/DASH live streams. "
        "Supports 300–350 concurrent streams with real-time QoS/QoE metrics."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

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
    """Add X-Process-Time header to all responses."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}s"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    logger.debug(f"{request.method} {request.url.path}")
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        logger.exception(f"Unhandled error on {request.method} {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc)},
        )


# ── Routers ────────────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(health.router, prefix=API_PREFIX, tags=["Health"])
app.include_router(channels.router, prefix=API_PREFIX, tags=["Channels"])
app.include_router(metrics.router, prefix=API_PREFIX, tags=["Metrics"])
app.include_router(errors.router, prefix=API_PREFIX, tags=["Errors"])
app.include_router(dashboard.router, prefix=API_PREFIX, tags=["Dashboard"])
app.include_router(alerts.router, prefix=API_PREFIX, tags=["Alerts"])
app.include_router(reports.router, prefix=API_PREFIX, tags=["Reports"])


# ── Root ───────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "OTT/IPTV Monitor API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }
