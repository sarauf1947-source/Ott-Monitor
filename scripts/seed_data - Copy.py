"""
OTT Monitor - Seed Script
Populates the database with 300 sample channels for testing.
Run: docker compose exec api python scripts/seed_data.py
"""

import asyncio
import logging
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import AsyncSessionLocal, engine, Base
from db.models import Channel, StreamProtocol, ChannelStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GROUPS = ["Sports", "News", "Entertainment", "Kids", "Documentary", "Music", "Movies", "Regional"]
PROTOCOLS = [StreamProtocol.HLS, StreamProtocol.DASH]

# Realistic-looking stream URL patterns for simulation
URL_PATTERNS = [
    "https://stream{n}.example.com/live/{slug}/playlist.m3u8",
    "https://cdn{n}.broadcaster.net/hls/{slug}/index.m3u8",
    "https://live-origin{n}.tv/dash/{slug}/manifest.mpd",
    "https://media{n}.streamhost.io/channel/{slug}/stream.m3u8",
]

CHANNEL_NAME_PREFIXES = [
    "ESPN", "CNN", "BBC", "Fox", "NBC", "CBS", "HBO", "Sky", "BT", "Discovery",
    "National Geographic", "Animal Planet", "History", "Cartoon", "Disney",
    "MTV", "VH1", "Comedy Central", "Syfy", "AMC", "Showtime", "Starz",
    "Bloomberg", "CNBC", "MSNBC", "Al Jazeera", "France 24", "DW", "RT",
]

RESOLUTIONS = ["1920x1080", "1280x720", "3840x2160", "854x480"]
BITRATES = [1500, 2500, 3500, 5000, 8000, 15000]


def make_slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace("_", "-")


def generate_channels(count: int = 300) -> list[Channel]:
    channels = []
    used_names = set()

    for i in range(1, count + 1):
        prefix = random.choice(CHANNEL_NAME_PREFIXES)
        suffix = random.choice(["HD", "4K", "Sports", "News", "Plus", "2", "3", f"Ch{i}"])
        name = f"{prefix} {suffix}"
        # Ensure unique name
        while name in used_names:
            name = f"{prefix} {suffix} {i}"
        used_names.add(name)

        slug = make_slug(name)
        n = random.randint(1, 20)
        url_template = random.choice(URL_PATTERNS)
        stream_url = url_template.format(n=n, slug=slug)

        protocol = StreamProtocol.DASH if "mpd" in stream_url else StreamProtocol.HLS

        channels.append(Channel(
            name=name,
            stream_url=stream_url,
            protocol=protocol,
            group=random.choice(GROUPS),
            description=f"Auto-seeded channel #{i}",
            status=ChannelStatus.UNKNOWN,
            is_active=True,
            expected_bitrate=random.choice(BITRATES),
            expected_resolution=random.choice(RESOLUTIONS),
        ))

    return channels


async def seed():
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Seeding 300 sample channels...")
    async with AsyncSessionLocal() as session:
        # Check if already seeded
        from sqlalchemy import select, func
        count = (await session.execute(
            select(func.count(Channel.id))
        )).scalar_one()

        if count >= 300:
            logger.info(f"Database already has {count} channels — skipping seed.")
            return

        channels = generate_channels(300)
        session.add_all(channels)
        await session.commit()

    logger.info("✅ Successfully seeded 300 channels.")


if __name__ == "__main__":
    asyncio.run(seed())
