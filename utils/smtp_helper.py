# -*- coding: utf-8 -*-
"""
utils/smtp_helper.py
DB-aware SMTP sender for OTT Monitor v2.2.

Priority order for SMTP config:
  1. SystemSettings table (set via Settings page in the UI)
  2. config.settings (environment variables / .env file)

This bridges the gap where SMTP was configured in the UI but
utils/alerts.py was reading only from environment variables.
"""
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

_smtp_cache: tuple[float, Optional[dict]] = (0.0, None)


async def get_smtp_config_from_db() -> Optional[dict]:
    """Read SMTP config from SystemSettings table. Returns None if not configured."""
    try:
        from db.database import AsyncSessionLocal
        from db.models import SystemSettings
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            rows = await db.execute(
                select(SystemSettings).where(SystemSettings.category == "smtp")
            )
            settings_rows = rows.scalars().all()
            if not settings_rows:
                return None
            cfg = {r.key: r.value for r in settings_rows}
            if not cfg.get("host") or not cfg.get("username"):
                return None
            return cfg
    except Exception as exc:
        logger.debug(f"Could not read SMTP config from DB: {exc}")
        return None


def _get_smtp_config_from_env() -> Optional[dict]:
    """Read SMTP config from environment variables."""
    from config import settings
    if not settings.SMTP_USER or not settings.SMTP_PASS:
        return None
    return {
        "host":       settings.SMTP_HOST,
        "port":       str(settings.SMTP_PORT),
        "username":   settings.SMTP_USER,
        "password":   settings.SMTP_PASS,
        "from_email": settings.ALERT_FROM,
        "from_name":  "OTT Monitor",
        "use_tls":    "true",
    }


async def resolve_smtp_config() -> Optional[dict]:
    """Return SMTP config from DB, falling back to env vars."""
    global _smtp_cache
    from config import settings

    cached_until, cached_value = _smtp_cache
    if cached_until > time.monotonic():
        return cached_value

    cfg = await get_smtp_config_from_db()
    if cfg:
        logger.debug("SMTP: using config from SystemSettings DB")
        _smtp_cache = (time.monotonic() + max(5, settings.ALERT_CONFIG_CACHE_TTL), cfg)
        return cfg
    cfg = _get_smtp_config_from_env()
    if cfg:
        logger.debug("SMTP: using config from environment variables")
        _smtp_cache = (time.monotonic() + max(5, settings.ALERT_CONFIG_CACHE_TTL), cfg)
        return cfg
    _smtp_cache = (time.monotonic() + max(5, settings.ALERT_CONFIG_CACHE_TTL), None)
    return None


def send_email_sync(cfg: dict, to_addresses: list, subject: str,
                    body_html: str, body_text: str = "") -> bool:
    """
    Send an email synchronously using the provided SMTP config dict.
    Safe to call from asyncio.to_thread().
    """
    host     = cfg.get("host", "")
    port     = int(cfg.get("port", 587))
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    from_email = cfg.get("from_email") or username
    from_name  = cfg.get("from_name", "OTT Monitor")
    use_tls  = str(cfg.get("use_tls", "true")).lower() == "true"

    if not host:
        logger.warning("SMTP: host not configured")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{from_name} <{from_email}>"
        msg["To"]      = ", ".join(to_addresses)
        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(host, port, timeout=20) as srv:
            srv.ehlo()
            if use_tls:
                srv.starttls()
                srv.ehlo()
            if username and password:
                srv.login(username, password)
            srv.sendmail(from_email, to_addresses, msg.as_string())

        logger.info(f"SMTP: email sent to {to_addresses} subject={subject!r}")
        return True
    except Exception as exc:
        logger.error(f"SMTP send failed: {exc}")
        return False


async def send_email_async(to_addresses: list, subject: str,
                           body_html: str, body_text: str = "") -> bool:
    """Send email using DB or env SMTP config. Async wrapper."""
    import asyncio
    cfg = await resolve_smtp_config()
    if not cfg:
        logger.warning("SMTP: no configuration found in DB or environment")
        return False
    return await asyncio.to_thread(
        send_email_sync, cfg, to_addresses, subject, body_html, body_text
    )
