"""
OTT Monitor - Monitoring Worker
Fetches assigned channels, runs stream analysis, stores results, triggers alerts.
Designed to run as multiple parallel workers (~20 streams each).
"""

import asyncio
import logging
import os
import signal
import time
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, update

from config import settings
from db.database import AsyncSessionLocal
from db.models import Alert, Channel, ChannelStatus, Error, ErrorSeverity, ErrorType, Metric
from utils.alerts import dispatch_alert
from utils.cache import CacheKeys, cache_delete, cache_set
from workers.stream_analyzer import StreamAnalysisResult, analyze_stream

logger = logging.getLogger(__name__)

# Worker ID from environment (set in docker-compose --scale)
WORKER_ID = int(os.environ.get("WORKER_ID", 0))
WORKER_INDEX = int(os.environ.get("WORKER_INDEX", 0))


async def process_channel(channel: Channel) -> None:
    """Analyze a single channel, persist metrics, and handle errors/alerts."""
    logger.debug(f"[W{WORKER_ID}] Checking channel: {channel.name}")
    analysis = await analyze_stream(str(channel.stream_url))

    async with AsyncSessionLocal() as session:
        try:
            await _persist_metric(session, channel, analysis)
            new_status = await _determine_status(analysis)
            await _update_channel_status(session, channel, new_status, analysis)
            await _process_errors(session, channel, analysis, new_status)
            await session.commit()

            # Invalidate cached status
            await cache_delete(CacheKeys.channel_status(str(channel.id)))
            await cache_delete(CacheKeys.channel_metrics(str(channel.id)))

        except Exception as e:
            logger.exception(f"Error persisting results for channel {channel.name}: {e}")
            await session.rollback()


async def _persist_metric(
    session, channel: Channel, analysis: StreamAnalysisResult
) -> None:
    """Write a new metric row."""
    metric = Metric(
        channel_id=channel.id,
        timestamp=datetime.now(timezone.utc),
        bitrate=analysis.bitrate_kbps,
        resolution_width=analysis.resolution_width,
        resolution_height=analysis.resolution_height,
        fps=analysis.fps,
        codec_video=analysis.codec_video,
        codec_audio=analysis.codec_audio,
        audio_level=analysis.audio_level_dbfs,
        audio_sample_rate=analysis.audio_sample_rate,
        response_time=analysis.response_time_ms,
        segment_duration=analysis.segment_duration,
        video_jitter=analysis.video_jitter_ms,
        is_available=analysis.is_available,
    )
    session.add(metric)


async def _determine_status(analysis: StreamAnalysisResult) -> ChannelStatus:
    """Map analysis results to a channel status."""
    if not analysis.is_available:
        return ChannelStatus.DOWN

    severities = {e["severity"] for e in analysis.detected_errors}
    if ErrorSeverity.CRITICAL in severities:
        return ChannelStatus.ERROR
    if ErrorSeverity.MAJOR in severities or ErrorSeverity.WARNING in severities:
        return ChannelStatus.WARNING
    return ChannelStatus.UP


async def _update_channel_status(
    session, channel: Channel, new_status: ChannelStatus, analysis: StreamAnalysisResult
) -> None:
    """Update channel status and last_checked_at."""
    now = datetime.now(timezone.utc)
    await session.execute(
        update(Channel)
        .where(Channel.id == channel.id)
        .values(
            status=new_status,
            last_checked_at=now,
            updated_at=now,
        )
    )

    # Cache the latest status for the dashboard
    await cache_set(
        CacheKeys.channel_status(str(channel.id)),
        {
            "status": new_status,
            "bitrate": analysis.bitrate_kbps,
            "resolution": (
                f"{analysis.resolution_width}x{analysis.resolution_height}"
                if analysis.resolution_width else None
            ),
            "fps": analysis.fps,
            "audio_level": analysis.audio_level_dbfs,
            "response_time": analysis.response_time_ms,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
        ttl=settings.REDIS_TTL_CHANNEL,
    )


async def _process_errors(
    session, channel: Channel, analysis: StreamAnalysisResult, status: ChannelStatus
) -> None:
    """Persist detected errors and create alerts for actionable issues."""
    # Resolve previously active errors if stream is healthy
    if status == ChannelStatus.UP:
        now = datetime.now(timezone.utc)
        await session.execute(
            update(Error)
            .where(Error.channel_id == channel.id, Error.is_active == True)
            .values(is_active=False, resolved_at=now)
        )
        # Resolve open alerts
        await session.execute(
            update(Alert)
            .where(
                Alert.channel_id == channel.id,
                Alert.status == "OPEN",
            )
            .values(status="RESOLVED", resolved_at=now)
        )

    for err in analysis.detected_errors:
        error_row = Error(
            channel_id=channel.id,
            timestamp=datetime.now(timezone.utc),
            error_type=err["error_type"],
            severity=err["severity"],
            message=err["message"],
            is_active=True,
        )
        session.add(error_row)

        # Create alert for CRITICAL/MAJOR errors only
        if err["severity"] in (ErrorSeverity.CRITICAL, ErrorSeverity.MAJOR):
            alert = Alert(
                channel_id=channel.id,
                alert_type=err["error_type"],
                severity=err["severity"],
                message=err["message"],
                triggered_at=datetime.now(timezone.utc),
                notification_sent=False,
            )
            session.add(alert)
            await session.flush()  # Get alert.id before dispatching

            # Fire notifications asynchronously (don't await — don't block the worker)
            asyncio.create_task(dispatch_alert(alert, channel.name))
            await session.execute(
                update(Alert)
                .where(Alert.id == alert.id)
                .values(notification_sent=True)
            )


class MonitorWorker:
    """
    Worker process that continuously monitors a partition of channels.
    Each worker handles ~20 channels and checks them every MONITOR_INTERVAL seconds.
    """

    def __init__(self, worker_id: int = 0, total_workers: int = 1):
        self.worker_id = worker_id
        self.total_workers = total_workers
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def get_assigned_channels(self) -> List[Channel]:
        """
        Fetch channels assigned to this worker.
        Assignment is based on modulo partitioning: channel_index % total_workers == worker_id.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Channel).where(Channel.is_active == True).order_by(Channel.created_at)
            )
            all_channels = result.scalars().all()

        assigned = [
            ch for i, ch in enumerate(all_channels)
            if i % self.total_workers == self.worker_id
        ]
        logger.info(
            f"[W{self.worker_id}] Assigned {len(assigned)} of {len(all_channels)} channels"
        )
        return assigned

    async def run_cycle(self) -> None:
        """Run one monitoring cycle: fetch channels → analyze in parallel → persist."""
        channels = await self.get_assigned_channels()
        if not channels:
            logger.warning(f"[W{self.worker_id}] No channels assigned — sleeping")
            return

        start = time.monotonic()
        logger.info(f"[W{self.worker_id}] Starting check cycle for {len(channels)} channels")

        # Process channels concurrently (batched to avoid overwhelming network)
        batch_size = 5
        for i in range(0, len(channels), batch_size):
            batch = channels[i : i + batch_size]
            await asyncio.gather(
                *[process_channel(ch) for ch in batch],
                return_exceptions=True,
            )

        elapsed = time.monotonic() - start
        logger.info(f"[W{self.worker_id}] Cycle complete in {elapsed:.1f}s")

        # Invalidate dashboard summary cache after each cycle
        await cache_delete("ott:dashboard:summary")

    async def run(self) -> None:
        """Main worker loop."""
        self.running = True
        logger.info(
            f"[W{self.worker_id}] Worker started "
            f"(interval={settings.MONITOR_INTERVAL}s, "
            f"simulate={settings.SIMULATE_MODE})"
        )

        # Register signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown_event.set)

        while not self._shutdown_event.is_set():
            try:
                await self.run_cycle()
            except Exception as e:
                logger.exception(f"[W{self.worker_id}] Unexpected error in cycle: {e}")

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=settings.MONITOR_INTERVAL,
                )
                break  # Shutdown requested
            except asyncio.TimeoutError:
                pass  # Normal — interval elapsed, start next cycle

        logger.info(f"[W{self.worker_id}] Worker shutting down gracefully")


async def main():
    """Entrypoint for the worker process."""
    import sys
    from utils.logger import setup_logging
    setup_logging()

    worker_id = int(os.environ.get("WORKER_ID", 0))
    total_workers = int(os.environ.get("TOTAL_WORKERS", 1))

    worker = MonitorWorker(worker_id=worker_id, total_workers=total_workers)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
