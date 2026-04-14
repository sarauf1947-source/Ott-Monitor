# -*- coding: utf-8 -*-
"""OTT Monitor - Monitoring Worker"""
import asyncio
import logging
import os
import signal
import socket
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, update

from config import settings
from db.database import AsyncSessionLocal
from db.models import Alert, AlertStatus, Channel, ChannelStatus, Error, ErrorSeverity, Metric
from utils.alerts import send_alert_notification
from utils.cache import CacheKeys, cache_delete, cache_set, redis_client
from workers.stream_analyzer import analyze_stream

logger = logging.getLogger(__name__)


def _resolve_worker_shard() -> tuple[int | None, int]:
    worker_id_raw = os.environ.get("WORKER_ID")
    total_workers = max(1, int(os.environ.get("TOTAL_WORKERS", 1)))

    if worker_id_raw is None:
        return None, total_workers

    worker_id = int(worker_id_raw)
    if worker_id < 0:
        logger.warning("WORKER_ID=%s is invalid; using Redis shard discovery", worker_id_raw)
        return None, total_workers
    if worker_id >= total_workers:
        logger.warning(
            "WORKER_ID=%s is outside TOTAL_WORKERS=%s; using Redis shard discovery",
            worker_id,
            total_workers,
        )
        return None, total_workers
    return worker_id, total_workers


@dataclass(frozen=True)
class PendingAlert:
    alert_id: str
    channel_id: str
    channel_name: str


@dataclass
class ChannelProcessingResult:
    channel_id: str
    channel_name: str
    is_available: bool
    error_count: int
    pending_alerts: list[PendingAlert] = field(default_factory=list)


class NotificationDispatcher:
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self._queue: asyncio.Queue[tuple[PendingAlert, int]] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []
        self._pending_ids: set[str] = set()
        self._running = False

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        worker_count = max(1, settings.ALERT_DISPATCH_CONCURRENCY)
        self._tasks = [
            asyncio.create_task(self._run_consumer(slot), name=f"alert-dispatch-{self.worker_id}-{slot}")
            for slot in range(worker_count)
        ]

    async def stop(self) -> None:
        self._running = False
        for _ in self._tasks:
            await self._queue.put((PendingAlert("", "", ""), -1))
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._pending_ids.clear()

    async def enqueue(self, pending_alert: PendingAlert) -> bool:
        if not pending_alert.alert_id or pending_alert.alert_id in self._pending_ids:
            return False
        self._pending_ids.add(pending_alert.alert_id)
        await self._queue.put((pending_alert, 0))
        return True

    async def _run_consumer(self, slot: int) -> None:
        while True:
            pending_alert, attempt = await self._queue.get()
            try:
                if attempt < 0:
                    return
                await self._dispatch_one(pending_alert, attempt)
            finally:
                self._queue.task_done()

    async def _dispatch_one(self, pending_alert: PendingAlert, attempt: int) -> None:
        try:
            async with AsyncSessionLocal() as session:
                row = await session.execute(
                    select(Alert).where(Alert.id == pending_alert.alert_id)
                )
                alert = row.scalar_one_or_none()
            if not alert:
                logger.warning("Alert %s no longer exists; dropping notification", pending_alert.alert_id)
                self._pending_ids.discard(pending_alert.alert_id)
                return
            if alert.notification_sent or alert.status != AlertStatus.OPEN:
                self._pending_ids.discard(pending_alert.alert_id)
                return

            outcome = await send_alert_notification(alert, pending_alert.channel_name)
            if outcome.delivered or not outcome.retryable:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(Alert)
                        .where(Alert.id == pending_alert.alert_id)
                        .values(notification_sent=True)
                    )
                    await session.commit()
                self._pending_ids.discard(pending_alert.alert_id)
                if outcome.delivered:
                    logger.info("Alert %s delivered by worker %s", pending_alert.alert_id, self.worker_id)
                else:
                    logger.info("Alert %s skipped by notification policy on worker %s", pending_alert.alert_id, self.worker_id)
                return
        except Exception as exc:
            logger.exception("Alert delivery failed for %s on attempt %s: %s", pending_alert.alert_id, attempt + 1, exc)

        if not self._running:
            self._pending_ids.discard(pending_alert.alert_id)
            return

        backoff = min(60, max(5, settings.WORKER_RETRY_DELAY * (attempt + 1)))
        logger.warning(
            "Alert %s was not delivered by worker %s; retrying in %ss",
            pending_alert.alert_id,
            self.worker_id,
            backoff,
        )
        await asyncio.sleep(backoff)
        await self._queue.put((pending_alert, attempt + 1))


async def process_channel(channel: Channel) -> ChannelProcessingResult:
    analysis = await analyze_stream(str(channel.stream_url))
    pending_alerts: list[PendingAlert] = []
    async with AsyncSessionLocal() as session:
        try:
            await _persist_metric(session, channel, analysis)
            new_status = await _determine_status(analysis)
            await _update_channel_status(session, channel, new_status, analysis)
            pending_alerts = await _process_errors(session, channel, analysis, new_status)
            await session.commit()
            await cache_delete(CacheKeys.channel_status(str(channel.id)))
            await cache_delete(CacheKeys.channel_metrics(str(channel.id)))
        except Exception as e:
            logger.exception(f"Error persisting channel {channel.name}: {e}")
            await session.rollback()
            return ChannelProcessingResult(
                channel_id=str(channel.id),
                channel_name=channel.name,
                is_available=False,
                error_count=max(1, len(analysis.detected_errors)),
            )

    return ChannelProcessingResult(
        channel_id=str(channel.id),
        channel_name=channel.name,
        is_available=analysis.is_available,
        error_count=len(analysis.detected_errors),
        pending_alerts=pending_alerts,
    )


async def _persist_metric(session, channel, analysis):
    session.add(Metric(
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
    ))


async def _determine_status(analysis):
    if not analysis.is_available:
        return ChannelStatus.DOWN
    severities = {e["severity"] for e in analysis.detected_errors}
    if ErrorSeverity.CRITICAL in severities:
        return ChannelStatus.ERROR
    if ErrorSeverity.MAJOR in severities or ErrorSeverity.WARNING in severities:
        return ChannelStatus.WARNING
    return ChannelStatus.UP


async def _update_channel_status(session, channel, new_status, analysis):
    now = datetime.now(timezone.utc)
    await session.execute(
        update(Channel)
        .where(Channel.id == channel.id)
        .values(status=new_status, last_checked_at=now, updated_at=now)
    )
    await cache_set(
        CacheKeys.channel_status(str(channel.id)),
        {
            "status": new_status,
            "bitrate": analysis.bitrate_kbps,
            "resolution": (
                f"{analysis.resolution_width}x{analysis.resolution_height}"
                if analysis.resolution_width
                else None
            ),
            "fps": analysis.fps,
            "audio_level": analysis.audio_level_dbfs,
            "response_time": analysis.response_time_ms,
            "checked_at": now.isoformat(),
        },
        ttl=settings.REDIS_TTL_CHANNEL,
    )


async def _process_errors(session, channel, analysis, status) -> list[PendingAlert]:
    pending_alerts: list[PendingAlert] = []
    if status == ChannelStatus.UP:
        now = datetime.now(timezone.utc)
        await session.execute(
            update(Error)
            .where(Error.channel_id == channel.id, Error.is_active == True)
            .values(is_active=False, resolved_at=now)
        )
        await session.execute(
            update(Alert)
            .where(Alert.channel_id == channel.id, Alert.status == AlertStatus.OPEN)
            .values(status=AlertStatus.RESOLVED, resolved_at=now)
        )
        return pending_alerts

    for err in analysis.detected_errors:
        session.add(Error(
            channel_id=channel.id,
            timestamp=datetime.now(timezone.utc),
            error_type=err["error_type"],
            severity=err["severity"],
            message=err["message"],
            is_active=True,
        ))
        if err["severity"] not in (ErrorSeverity.CRITICAL, ErrorSeverity.MAJOR):
            continue

        existing_open = await session.execute(
            select(Alert.id).where(
                Alert.channel_id == channel.id,
                Alert.alert_type == err["error_type"],
                Alert.status == AlertStatus.OPEN,
            )
        )
        if existing_open.first():
            continue

        alert = Alert(
            channel_id=channel.id,
            alert_type=err["error_type"],
            severity=err["severity"],
            message=err["message"],
            triggered_at=datetime.now(timezone.utc),
            notification_sent=False,
        )
        session.add(alert)
        await session.flush()
        pending_alerts.append(
            PendingAlert(
                alert_id=str(alert.id),
                channel_id=str(channel.id),
                channel_name=channel.name,
            )
        )

    return pending_alerts


class MonitorWorker:
    def __init__(self, worker_id: int | None = None, total_workers: int = 1):
        self.worker_id = worker_id
        self.total_workers = total_workers
        self.running = False
        self._shutdown_event = asyncio.Event()
        self.instance_id = os.environ.get("HOSTNAME") or socket.gethostname() or f"worker-{uuid.uuid4().hex[:8]}"
        self._dispatcher = NotificationDispatcher(worker_id=worker_id or 0)
        self._worker_key = f"worker:status:{self.instance_id}"
        self._shard_key: str | None = None

    async def _claim_worker_shard(self) -> None:
        if self.worker_id is not None:
            self._shard_key = f"worker:shard:{self.worker_id}"
            await redis_client.set(self._shard_key, self.instance_id, ex=settings.WORKER_STATUS_TTL)
            self._dispatcher.worker_id = self.worker_id
            return

        for candidate in range(self.total_workers):
            shard_key = f"worker:shard:{candidate}"
            claimed = await redis_client.set(
                shard_key,
                self.instance_id,
                nx=True,
                ex=settings.WORKER_STATUS_TTL,
            )
            if claimed:
                self.worker_id = candidate
                self._shard_key = shard_key
                self._dispatcher.worker_id = candidate
                logger.info("Worker instance %s claimed shard %s/%s", self.instance_id, candidate, self.total_workers)
                return

            owner = await redis_client.get(shard_key)
            if owner == self.instance_id:
                await redis_client.expire(shard_key, settings.WORKER_STATUS_TTL)
                self.worker_id = candidate
                self._shard_key = shard_key
                self._dispatcher.worker_id = candidate
                return

        logger.warning(
            "No free shard found for %s across %s slots; falling back to shard 0/1",
            self.instance_id,
            self.total_workers,
        )
        self.worker_id = 0
        self.total_workers = 1
        self._dispatcher.worker_id = 0

    async def get_assigned_channels(self) -> List[Channel]:
        shard_id = self.worker_id if self.worker_id is not None else 0
        async with AsyncSessionLocal() as session:
            all_channels = (
                await session.execute(
                    select(Channel).where(Channel.is_active == True).order_by(Channel.created_at)
                )
            ).scalars().all()
        assigned = [ch for i, ch in enumerate(all_channels) if i % self.total_workers == shard_id]
        logger.info(f"[W{shard_id}] Assigned {len(assigned)} of {len(all_channels)} channels")
        return assigned

    async def _queue_pending_alerts(self, channels: List[Channel]) -> None:
        channel_name_by_id = {str(channel.id): channel.name for channel in channels}
        channel_ids = [channel.id for channel in channels]
        if not channel_name_by_id:
            return

        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(Alert.id, Alert.channel_id)
                .where(
                    Alert.notification_sent == False,
                    Alert.status == AlertStatus.OPEN,
                    Alert.channel_id.in_(channel_ids),
                )
                .order_by(Alert.triggered_at.asc())
            )
            for alert_id, channel_id in rows.all():
                await self._dispatcher.enqueue(
                    PendingAlert(
                        alert_id=str(alert_id),
                        channel_id=str(channel_id),
                        channel_name=channel_name_by_id.get(str(channel_id), str(channel_id)),
                    )
                )

    async def _publish_worker_status(
        self,
        assigned: int,
        ok_count: int,
        error_count: int,
        last_cycle_sec: float,
    ) -> None:
        shard_id = self.worker_id if self.worker_id is not None else 0
        try:
            payload = {
                "worker_id": self.instance_id,
                "shard_id": shard_id,
                "streams_assigned": assigned,
                "streams_ok": ok_count,
                "streams_error": error_count,
                "last_cycle_sec": round(last_cycle_sec, 2),
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "notification_queue_depth": self._dispatcher.queue_depth,
                "probe_concurrency": max(1, settings.STREAMS_PER_WORKER),
                "total_workers": self.total_workers,
            }
            await redis_client.hset(self._worker_key, mapping=payload)
            await redis_client.expire(self._worker_key, settings.WORKER_STATUS_TTL)
            if self._shard_key:
                await redis_client.expire(self._shard_key, settings.WORKER_STATUS_TTL)
        except Exception as exc:
            logger.warning("Failed to publish worker status for %s: %s", self.instance_id, exc)

    async def run_cycle(self) -> None:
        channels = await self.get_assigned_channels()
        await self._queue_pending_alerts(channels)
        if not channels:
            await self._publish_worker_status(0, 0, 0, 0.0)
            return

        start = time.monotonic()
        concurrency = max(1, settings.STREAMS_PER_WORKER)
        ok_count = 0
        error_count = 0
        shard_id = self.worker_id if self.worker_id is not None else 0

        for i in range(0, len(channels), concurrency):
            batch = channels[i:i + concurrency]
            results = await asyncio.gather(*(process_channel(ch) for ch in batch), return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    error_count += 1
                    logger.error("[W%s] Channel task failed: %s", shard_id, result)
                    continue
                ok_count += 1 if result.is_available else 0
                error_count += 0 if result.is_available else 1
                for pending_alert in result.pending_alerts:
                    await self._dispatcher.enqueue(pending_alert)

        duration = time.monotonic() - start
        logger.info(f"[W{shard_id}] Cycle complete in {duration:.1f}s")
        await self._publish_worker_status(len(channels), ok_count, error_count, duration)
        await cache_delete(CacheKeys.DASHBOARD_SUMMARY)

    async def run(self) -> None:
        self.running = True
        await self._claim_worker_shard()
        await self._dispatcher.start()
        await self._publish_worker_status(0, 0, 0, 0.0)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown_event.set)
        while not self._shutdown_event.is_set():
            try:
                await self.run_cycle()
            except Exception as e:
                logger.exception(f"[W{self.worker_id}] Cycle error: {e}")
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=settings.MONITOR_INTERVAL)
                break
            except asyncio.TimeoutError:
                pass
        await self._dispatcher.stop()
        try:
            await redis_client.delete(self._worker_key)
            if self._shard_key:
                owner = await redis_client.get(self._shard_key)
                if owner == self.instance_id:
                    await redis_client.delete(self._shard_key)
        except Exception:
            pass


async def main():
    from utils.logger import setup_logging

    setup_logging()
    worker_id, total_workers = _resolve_worker_shard()
    if worker_id is None:
        logger.info("Starting worker with Redis shard discovery across %s shard(s)", total_workers)
    else:
        logger.info("Starting worker shard %s/%s", worker_id, total_workers)
    worker = MonitorWorker(worker_id=worker_id, total_workers=total_workers)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
