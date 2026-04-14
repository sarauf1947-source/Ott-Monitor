# -*- coding: utf-8 -*-
"""Seed 300 sample channels. Run: docker compose exec api python scripts/seed_data.py"""
import asyncio, logging, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import AsyncSessionLocal, engine, Base
from db.models import Channel, StreamProtocol, ChannelStatus
from sqlalchemy import select, func

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GROUPS = ["Sports","News","Entertainment","Kids","Documentary","Music","Movies","Regional"]
NAMES  = ["ESPN","CNN","BBC","Fox","NBC","CBS","HBO","Sky","BT","Discovery",
          "NatGeo","Animal Planet","History","Cartoon","Disney","MTV","Comedy Central",
          "Bloomberg","CNBC","Al Jazeera","France 24","DW","Syfy","AMC","Showtime"]
URL_PATTERNS = [
    "https://stream{n}.example.com/live/{slug}/playlist.m3u8",
    "https://cdn{n}.broadcaster.net/hls/{slug}/index.m3u8",
    "https://live{n}.tv/dash/{slug}/manifest.mpd",
]
RESOLUTIONS = ["1920x1080","1280x720","3840x2160","854x480"]
BITRATES    = [1500,2500,3500,5000,8000,15000]

async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        count = (await session.execute(select(func.count(Channel.id)))).scalar_one()
        if count >= 300:
            logger.info(f"Already has {count} channels -- skipping"); return
        used = set(); channels = []
        for i in range(1, 301):
            prefix = random.choice(NAMES); suffix = random.choice(["HD","4K","Sports","News","Plus",f"Ch{i}"])
            name = f"{prefix} {suffix}"
            while name in used: name = f"{prefix} {suffix} {i}"
            used.add(name)
            slug = name.lower().replace(" ","-"); n = random.randint(1,20)
            url = random.choice(URL_PATTERNS).format(n=n, slug=slug)
            channels.append(Channel(name=name, stream_url=url,
                protocol=StreamProtocol.DASH if "mpd" in url else StreamProtocol.HLS,
                group=random.choice(GROUPS), description=f"Sample channel #{i}",
                status=ChannelStatus.UNKNOWN, is_active=True,
                expected_bitrate=random.choice(BITRATES), expected_resolution=random.choice(RESOLUTIONS)))
        session.add_all(channels); await session.commit()
    logger.info("Seeded 300 channels.")

if __name__ == "__main__":
    asyncio.run(seed())
