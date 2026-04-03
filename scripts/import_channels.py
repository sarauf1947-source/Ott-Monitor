"""
OTT Monitor - CSV Channel Import
Usage: docker compose exec api python scripts/import_channels.py channels.csv

CSV format (with header):
  name,stream_url,protocol,group,description,expected_bitrate,expected_resolution
"""

import asyncio
import csv
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import AsyncSessionLocal, engine, Base
from db.models import Channel, StreamProtocol, ChannelStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_COLS = {"name", "stream_url"}


async def import_csv(filepath: str):
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        sys.exit(1)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    imported = skipped = errors = 0

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = set(reader.fieldnames or [])
        missing = REQUIRED_COLS - cols
        if missing:
            logger.error(f"CSV missing required columns: {missing}")
            sys.exit(1)

        async with AsyncSessionLocal() as session:
            for i, row in enumerate(reader, start=2):
                name = row.get("name", "").strip()
                url = row.get("stream_url", "").strip()

                if not name or not url:
                    logger.warning(f"Row {i}: skipping — name or stream_url empty")
                    skipped += 1
                    continue

                try:
                    protocol_str = row.get("protocol", "HLS").strip().upper()
                    protocol = StreamProtocol(protocol_str) if protocol_str in StreamProtocol._value2member_map_ else StreamProtocol.HLS

                    channel = Channel(
                        name=name,
                        stream_url=url,
                        protocol=protocol,
                        group=row.get("group", "").strip() or None,
                        description=row.get("description", "").strip() or None,
                        status=ChannelStatus.UNKNOWN,
                        is_active=True,
                        expected_bitrate=int(row["expected_bitrate"]) if row.get("expected_bitrate") else None,
                        expected_resolution=row.get("expected_resolution", "").strip() or None,
                    )
                    session.add(channel)
                    imported += 1

                    if imported % 50 == 0:
                        await session.flush()
                        logger.info(f"  Imported {imported} channels so far...")

                except Exception as e:
                    logger.error(f"Row {i}: error — {e}")
                    errors += 1

            await session.commit()

    logger.info(f"✅ Import complete: {imported} imported, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_channels.py <path/to/channels.csv>")
        sys.exit(1)
    asyncio.run(import_csv(sys.argv[1]))
