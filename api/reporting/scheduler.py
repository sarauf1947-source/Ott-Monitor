# -*- coding: utf-8 -*-
"""APScheduler-based scheduled report runner. api/reporting/scheduler.py"""
import asyncio
import json
import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger    = logging.getLogger("ott.scheduler")
scheduler = AsyncIOScheduler()

BASE_URL     = os.getenv("INTERNAL_API_URL",    "http://localhost:8000")
SYSTEM_TOKEN = os.getenv("SCHEDULER_API_TOKEN", "")
_DAYS        = {"daily": 1, "weekly": 7, "monthly": 30}


async def _run_report(report_id: int, session_factory) -> None:
    async with session_factory() as db:
        try:
            from db.models import ScheduledReport
            from sqlalchemy import select
            res    = await db.execute(
                select(ScheduledReport).where(
                    ScheduledReport.id == report_id,
                    ScheduledReport.is_active == True,  # noqa: E712
                )
            )
            report = res.scalar_one_or_none()
            if not report:
                return

            channel_ids = json.loads(report.channel_ids) if report.channel_ids else []
            if not channel_ids:
                from db.models import Channel
                rows        = (await db.execute(select(Channel.id))).fetchall()
                channel_ids = [str(r[0]) for r in rows]

            days    = _DAYS.get(report.frequency, 7)
            headers = {"Authorization": f"Bearer {SYSTEM_TOKEN}"}

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{BASE_URL}/api/v1/reports/bulk?days={days}",
                    json=channel_ids,
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.error(f"Report {report_id} bulk fetch failed: {resp.status_code}")
                    return
                report_data = resp.json()

            recipients = json.loads(report.email_recipients) if report.email_recipients else []
            if recipients:
                await _send_email(report, report_data, recipients, db)
            if report.webhook_url:
                await _send_webhook(report, report_data)

            report.last_run_at = datetime.utcnow()
            report.next_run_at = datetime.utcnow() + timedelta(days=days)
            await db.commit()

        except Exception as exc:
            logger.exception(f"Scheduled report {report_id} failed: {exc}")
            await db.rollback()


async def _send_email(report, data: dict, recipients: list, db) -> None:
    from api.settings.settings_routes import _get
    host = await _get(db, "smtp", "host")
    if not host:
        return
    port       = int(await _get(db, "smtp", "port") or 587)
    username   = await _get(db, "smtp", "username")
    password   = await _get(db, "smtp", "password")
    from_email = await _get(db, "smtp", "from_email") or username
    use_tls    = (await _get(db, "smtp", "use_tls") or "true") == "true"
    body = (
        f"OTT Monitor Scheduled Report: {report.name}\n\n"
        f"Generated: {datetime.utcnow().isoformat()} UTC\n"
        f"Channels:  {data.get('report_count', 0)}\n"
    )
    try:
        msg = MIMEText(body)
        msg["Subject"] = f"[OTT Monitor] {report.name}"
        msg["From"]    = from_email
        msg["To"]      = ", ".join(recipients)
        with smtplib.SMTP(host, port, timeout=15) as s:
            if use_tls:
                s.starttls()
            if username and password:
                s.login(username, password)
            s.sendmail(from_email, recipients, msg.as_string())
    except Exception as exc:
        logger.error(f"Email delivery failed for report {report.id}: {exc}")


async def _send_webhook(report, data: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                report.webhook_url,
                json={"report": report.name, "data": data,
                      "generated_at": datetime.utcnow().isoformat()},
            )
    except Exception as exc:
        logger.warning(f"Webhook failed for report {report.id}: {exc}")


async def _reload_jobs(session_factory) -> None:
    async with session_factory() as db:
        try:
            from db.models import ScheduledReport
            from sqlalchemy import select
            res     = await db.execute(
                select(ScheduledReport).where(ScheduledReport.is_active == True)  # noqa: E712
            )
            reports = res.scalars().all()

            for job in scheduler.get_jobs():
                if job.id.startswith("report_"):
                    scheduler.remove_job(job.id)

            triggers = {
                "daily":   CronTrigger(hour=6,  minute=0),
                "weekly":  CronTrigger(day_of_week="mon", hour=6, minute=0),
                "monthly": CronTrigger(day=1,   hour=6, minute=0),
            }
            for r in reports:
                t = triggers.get(r.frequency)
                if t:
                    scheduler.add_job(
                        _run_report, trigger=t,
                        args=[r.id, session_factory],
                        id=f"report_{r.id}", replace_existing=True,
                    )
        except Exception as exc:
            logger.debug(f"Scheduler reload skipped: {exc}")


def setup_scheduler(async_session_factory) -> None:
    """Call once from api/main.py lifespan startup."""
    scheduler.add_job(
        _reload_jobs, "interval", hours=1,
        args=[async_session_factory],
        id="reload_jobs", replace_existing=True,
    )

    async def _startup():
        await asyncio.sleep(3)
        await _reload_jobs(async_session_factory)

    scheduler.add_job(_startup, "date", id="startup_load", replace_existing=True)
    scheduler.start()
