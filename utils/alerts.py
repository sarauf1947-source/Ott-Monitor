# -*- coding: utf-8 -*-
"""
utils/alerts.py  (v2.2)
Alerting engine: email + webhook notifications.
FIXED: send_email now uses smtp_helper which reads SMTP config from
       SystemSettings DB first, falling back to .env variables.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from sqlalchemy import select

from config import settings
from db.database import AsyncSessionLocal
from db.models import Alert, ErrorSeverity, SystemSettings

logger = logging.getLogger(__name__)

_config_lock = asyncio.Lock()
_alert_config_cache: tuple[float, dict[str, Any]] = (0.0, {})
_webhook_targets_cache: tuple[float, list["WebhookTarget"]] = (0.0, [])
_email_recipients_cache: tuple[float, list[str]] = (0.0, [])
_http_client: httpx.AsyncClient | None = None

_SEV_LABEL = {
    ErrorSeverity.CRITICAL: "CRITICAL",
    ErrorSeverity.MAJOR:    "MAJOR",
    ErrorSeverity.WARNING:  "WARNING",
    ErrorSeverity.INFO:     "INFO",
}

_SEV_COLOR = {
    ErrorSeverity.CRITICAL: "#dc2626",
    ErrorSeverity.MAJOR:    "#d97706",
    ErrorSeverity.WARNING:  "#7c3aed",
    ErrorSeverity.INFO:     "#2563eb",
}

_SEV_RANK = {
    ErrorSeverity.INFO: 0,
    ErrorSeverity.WARNING: 1,
    ErrorSeverity.MAJOR: 2,
    ErrorSeverity.CRITICAL: 3,
}


@dataclass
class WebhookTarget:
    name: str
    url: str


@dataclass
class NotificationAttempt:
    delivered: bool = False
    retryable: bool = True


def _cache_expiry() -> float:
    return time.monotonic() + max(5, settings.ALERT_CONFIG_CACHE_TTL)


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
        _http_client = httpx.AsyncClient(timeout=10, limits=limits)
    return _http_client


async def _load_alert_config() -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(SystemSettings).where(
                SystemSettings.category == "alert",
                SystemSettings.key == "config",
            )
        )
        config_row = row.scalar_one_or_none()
    if not config_row or not config_row.value:
        return {}
    try:
        return json.loads(config_row.value)
    except json.JSONDecodeError:
        logger.warning("Invalid alert config JSON in system settings")
        return {}


async def _get_alert_config() -> dict:
    global _alert_config_cache
    cached_until, cached_value = _alert_config_cache
    if cached_until > time.monotonic():
        return cached_value
    async with _config_lock:
        cached_until, cached_value = _alert_config_cache
        if cached_until > time.monotonic():
            return cached_value
        fresh = await _load_alert_config()
        _alert_config_cache = (_cache_expiry(), fresh)
        return fresh


async def _load_webhook_targets() -> list[WebhookTarget]:
    targets: list[WebhookTarget] = []
    if settings.WEBHOOK_URL:
        targets.append(WebhookTarget(name="Environment webhook", url=settings.WEBHOOK_URL))

    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(SystemSettings).where(
                SystemSettings.category == "webhook",
                SystemSettings.key == "list",
            )
        )
        hooks_row = row.scalar_one_or_none()

    if not hooks_row or not hooks_row.value:
        return targets

    try:
        hooks = json.loads(hooks_row.value)
    except json.JSONDecodeError:
        logger.warning("Invalid webhook list JSON in system settings")
        return targets

    for hook in hooks:
        url = str(hook.get("url", "")).strip()
        if not url or not hook.get("is_active", True):
            continue
        targets.append(WebhookTarget(name=hook.get("name", "Webhook"), url=url))
    return targets


async def _get_webhook_targets() -> list[WebhookTarget]:
    global _webhook_targets_cache
    cached_until, cached_value = _webhook_targets_cache
    if cached_until > time.monotonic():
        return cached_value
    async with _config_lock:
        cached_until, cached_value = _webhook_targets_cache
        if cached_until > time.monotonic():
            return cached_value
        fresh = await _load_webhook_targets()
        _webhook_targets_cache = (_cache_expiry(), fresh)
        return fresh


def _build_discord_payload(alert: Alert, channel_name: str) -> dict:
    sev = _SEV_LABEL.get(alert.severity, str(alert.severity))
    color_hex = _SEV_COLOR.get(alert.severity, "#888888").lstrip("#")
    return {
        "content": f"[{sev}] OTT Alert for {channel_name}",
        "embeds": [{
            "title": str(alert.alert_type),
            "description": alert.message or "No additional details provided.",
            "color": int(color_hex, 16),
            "fields": [
                {"name": "Channel", "value": channel_name, "inline": True},
                {"name": "Severity", "value": sev, "inline": True},
                {"name": "Triggered At", "value": alert.triggered_at.isoformat(), "inline": False},
            ],
        }],
    }


def _resolve_min_severity(raw_value: str | None) -> ErrorSeverity:
    normalized = (raw_value or "major").strip().upper()
    if normalized == "CRITICAL":
        return ErrorSeverity.CRITICAL
    if normalized == "WARNING":
        return ErrorSeverity.WARNING
    return ErrorSeverity.MAJOR


def _meets_min_severity(alert_severity: ErrorSeverity, minimum: ErrorSeverity) -> bool:
    return _SEV_RANK.get(alert_severity, -1) >= _SEV_RANK.get(minimum, 0)


async def send_webhook(alert: Alert, channel_name: str) -> NotificationAttempt:
    """Send alert notifications to configured webhooks."""
    alert_cfg = await _get_alert_config()
    if not alert_cfg.get("enable_webhook", True):
        return NotificationAttempt(delivered=False, retryable=False)
    min_severity = _resolve_min_severity(alert_cfg.get("severity_email_min"))
    if not _meets_min_severity(alert.severity, min_severity):
        logger.info(
            "Webhook skipped for alert %s: severity %s below minimum %s",
            alert.id,
            alert.severity,
            min_severity,
        )
        return NotificationAttempt(delivered=False, retryable=False)
    targets = await _get_webhook_targets()
    if not targets:
        return NotificationAttempt(delivered=False, retryable=False)

    payload = _build_discord_payload(alert, channel_name)
    sent = False
    client = await _get_http_client()
    for target in targets:
        try:
            resp = await client.post(target.url, json=payload)
            resp.raise_for_status()
            logger.info("Webhook sent for alert %s via %s", alert.id, target.name)
            sent = True
        except Exception as exc:
            logger.error("Webhook failed for alert %s via %s: %s", alert.id, target.name, exc)
    return NotificationAttempt(delivered=sent, retryable=not sent)


async def _get_email_recipients() -> list[str]:
    global _email_recipients_cache
    cached_until, cached_value = _email_recipients_cache
    if cached_until > time.monotonic():
        return cached_value
    async with _config_lock:
        cached_until, cached_value = _email_recipients_cache
        if cached_until > time.monotonic():
            return cached_value
        to_list: list[str] = []
        try:
            alert_cfg = await _load_alert_config()
            recips = str(alert_cfg.get("email_recipients", "")).strip()
            if recips:
                to_list = [r.strip() for r in recips.split(",") if r.strip()]
        except Exception:
            to_list = []
        if not to_list and settings.ALERT_TO:
            to_list = [settings.ALERT_TO]
        _email_recipients_cache = (_cache_expiry(), to_list)
        return to_list


async def send_email(alert: Alert, channel_name: str) -> NotificationAttempt:
    """
    Send SMTP alert email.
    Reads SMTP config from SystemSettings DB first, then falls back to .env.
    """
    from utils.smtp_helper import resolve_smtp_config, send_email_sync

    cfg = await resolve_smtp_config()
    if not cfg:
        logger.debug("Alert email skipped: no SMTP configuration found")
        return NotificationAttempt(delivered=False, retryable=False)

    to_list = await _get_email_recipients()
    if not to_list:
        logger.debug("Alert email skipped: no recipients configured")
        return NotificationAttempt(delivered=False, retryable=False)

    sev = _SEV_LABEL.get(alert.severity, str(alert.severity))
    subject = f"[OTT Monitor] {sev} Alert: {channel_name} - {alert.alert_type}"

    body_html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif">
<h2 style="color:#1E3A5F">OTT Monitor - Stream Alert</h2>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
  <tr style="background:#1E3A5F;color:#fff">
    <th>Field</th><th>Value</th>
  </tr>
  <tr><td><b>Channel</b></td><td>{channel_name}</td></tr>
  <tr><td><b>Alert Type</b></td><td>{alert.alert_type}</td></tr>
  <tr><td><b>Severity</b></td>
    <td style="color:{_SEV_COLOR.get(alert.severity,'#333')};font-weight:bold">{sev}</td></tr>
  <tr><td><b>Message</b></td><td>{alert.message or 'No details'}</td></tr>
  <tr><td><b>Triggered At</b></td><td>{alert.triggered_at.isoformat()}</td></tr>
</table>
<p style="margin-top:20px;color:#666;font-size:12px">
  Log in to the OTT Monitor dashboard to acknowledge or resolve this alert.
</p>
</body></html>"""

    delivered = await asyncio.to_thread(send_email_sync, cfg, to_list, subject, body_html)
    return NotificationAttempt(delivered=delivered, retryable=not delivered)


async def send_alert_notification(alert: Alert, channel_name: str) -> NotificationAttempt:
    """Fire all configured notification channels for an alert."""
    results = await asyncio.gather(
        send_webhook(alert, channel_name),
        send_email(alert, channel_name),
        return_exceptions=True,
    )
    sent = False
    retryable = False
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Alert dispatch error: {r}")
            retryable = True
        else:
            sent = sent or r.delivered
            retryable = retryable or r.retryable
    if sent:
        return NotificationAttempt(delivered=True, retryable=False)
    return NotificationAttempt(delivered=False, retryable=retryable)


async def dispatch_alert(alert: Alert, channel_name: str) -> None:
    await send_alert_notification(alert, channel_name)


async def send_test_webhook(url: str, name: str = "Test Webhook") -> None:
    payload = {
        "content": "OTT Monitor webhook test",
        "embeds": [{
            "title": "Webhook Test",
            "description": "This is a test notification from OTT Monitor.",
            "color": int("2563eb", 16),
            "fields": [
                {"name": "Webhook", "value": name, "inline": True},
                {"name": "Status", "value": "Connectivity OK", "inline": True},
            ],
        }],
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
