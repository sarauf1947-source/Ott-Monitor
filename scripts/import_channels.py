# -*- coding: utf-8 -*-
"""CSV channel import. Usage: docker compose exec api python scripts/import_channels.py channels.csv"""
import asyncio, csv, logging, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import AsyncSessionLocal, engine, Base
from db.models import Channel, StreamProtocol, ChannelStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

async def import_csv(filepath):
    if not os.path.exists(filepath): logger.error(f"File not found: {filepath}"); sys.exit(1)
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    imported = skipped = errors = 0
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f); cols = set(reader.fieldnames or [])
        if not {"name","stream_url"} <= cols: logger.error("CSV needs name and stream_url columns"); sys.exit(1)
        async with AsyncSessionLocal() as session:
            for i, row in enumerate(reader, start=2):
                name = row.get("name","").strip(); url = row.get("stream_url","").strip()
                if not name or not url: skipped += 1; continue
                try:
                    proto = row.get("protocol","HLS").strip().upper()
                    session.add(Channel(name=name, stream_url=url,
                        protocol=StreamProtocol(proto) if proto in StreamProtocol._value2member_map_ else StreamProtocol.HLS,
                        group=row.get("group","").strip() or None,
                        description=row.get("description","").strip() or None,
                        status=ChannelStatus.UNKNOWN, is_active=True,
                        expected_bitrate=int(row["expected_bitrate"]) if row.get("expected_bitrate") else None,
                        expected_resolution=row.get("expected_resolution","").strip() or None))
                    imported += 1
                    if imported % 50 == 0: await session.flush(); logger.info(f"  {imported} imported...")
                except Exception as e: logger.error(f"Row {i}: {e}"); errors += 1
            await session.commit()
    logger.info(f"Done: {imported} imported, {skipped} skipped, {errors} errors")

if __name__ == "__main__":
    if len(sys.argv) < 2: print("Usage: python scripts/import_channels.py <file.csv>"); sys.exit(1)
    asyncio.run(import_csv(sys.argv[1]))
