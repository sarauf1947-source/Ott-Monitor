"""
OTT Monitor - Async Database Engine & Session Factory
Uses SQLAlchemy 2.x async with asyncpg driver.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import text

from config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DB_ECHO,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_hypertables() -> None:
    """
    Convert metrics and errors tables to TimescaleDB hypertables.
    Must be called after initial table creation. Safe to run repeatedly.
    """
    statements = [
        "SELECT create_hypertable('metrics', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)",
        "SELECT create_hypertable('errors', 'timestamp', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE)",
        "SELECT add_retention_policy('metrics', INTERVAL '90 days', if_not_exists => TRUE)",
        "SELECT add_retention_policy('errors', INTERVAL '180 days', if_not_exists => TRUE)",
        "ALTER TABLE metrics SET (timescaledb.compress, timescaledb.compress_segmentby = 'channel_id')",
        "SELECT add_compression_policy('metrics', INTERVAL '7 days', if_not_exists => TRUE)",
    ]

    async with AsyncSessionLocal() as session:
        for sql in statements:
            try:
                await session.execute(text(sql))
                await session.commit()
                logger.info(f"TimescaleDB: executed — {sql[:60]}...")
            except Exception as e:
                logger.warning(f"TimescaleDB step skipped (may already exist): {e}")
                await session.rollback()
