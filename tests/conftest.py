"""
OTT Monitor - Test Configuration & Fixtures
Uses an in-memory SQLite DB for unit tests.
"""

import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from db.database import Base, get_db
from db.models import Channel, ChannelStatus, StreamProtocol
from api.main import app

# ── In-memory SQLite for tests ──────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a fresh DB session, rolls back after each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yields an httpx AsyncClient wired to the test DB."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_channel(db_session: AsyncSession) -> Channel:
    """Creates and returns a single sample channel."""
    ch = Channel(
        id=uuid.uuid4(),
        name="Test Channel HD",
        stream_url="https://test.example.com/live/test/playlist.m3u8",
        protocol=StreamProtocol.HLS,
        group="Sports",
        status=ChannelStatus.UP,
        is_active=True,
        expected_bitrate=3500,
        expected_resolution="1920x1080",
    )
    db_session.add(ch)
    await db_session.flush()
    return ch
