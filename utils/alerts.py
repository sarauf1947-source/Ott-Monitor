"""
OTT Monitor - Alerting Engine
Handles email and webhook notifications for stream anomalies.
"""

import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

from config import settings
from db.models import Alert, ErrorSeverity

logger = logging.getLogger(__name__)

# Severity → emoji mapping for notifications
SEVERITY_EMOJI = {
    ErrorSeverity.CRITICAL: "🔴",
    ErrorSeverity.MAJOR: "🟡",
    ErrorSeverity.WARNING: "🟣",
    ErrorSeverity.INFO: "🔵",
}


async def send_webhook(alert: Alert, channel_name: str) -> bool:
    """
    Send a Slack-compatible webhook notification.
    Payload format: {"text": "...", "attachments": [...]}
    """
    if not settings.WEBHOOK_URL:
        logger.debug("Webhook URL not configured — skipping")
        return False

    emoji = SEVERITY_EMOJI.get(alert.severity, "⚠️")
    text = (
        f"{emoji} *OTT Alert [{alert.severity}]*\n"
        f"Channel: *{channel_name}*\n"
        f"Type: `{alert.alert_type}`\n"
        f"Message: {alert.message or 'No details'}\n"
        f"Time: {alert.triggered_at.isoformat()}"
    )

    payload = {
        "text": text,
        "attachments": [
            {
                "color": _severity_color(alert.severity),
                "fields": [
                    {"title": "Channel", "value": channel_name, "short": True},
                    {"title": "Alert Type", "value": alert.alert_type, "short": True},
                    {"title": "Severity", "value": alert.severity, "short": True},
                    {"title": "Status", "value": alert.status, "short": True},
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                settings.WEBHOOK_URL,
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            logger.info(f"Webhook sent for alert {alert.id} ({channel_name})")
            return True
    except Exception as e:
        logger.error(f"Webhook send failed for alert {alert.id}: {e}")
        return False


def send_email(alert: Alert, channel_name: str) -> bool:
    """
    Send an SMTP email notification (synchronous — run in executor if needed).
    """
    if not settings.SMTP_USER or not settings.SMTP_PASS:
        logger.debug("SMTP credentials not configured — skipping email")
        return False

    emoji = SEVERITY_EMOJI.get(alert.severity, "⚠️")
    subject = f"{emoji} OTT Alert [{alert.severity}]: {channel_name} — {alert.alert_type}"

    body_html = f"""
    <html><body>
    <h2>{emoji} OTT Monitor Alert</h2>
    <table border="1" cellpadding="8" cellspacing="0">
      <tr><th>Channel</th><td>{channel_name}</td></tr>
      <tr><th>Alert Type</th><td>{alert.alert_type}</td></tr>
      <tr><th>Severity</th><td>{alert.severity}</td></tr>
      <tr><th>Message</th><td>{alert.message or 'N/A'}</td></tr>
      <tr><th>Triggered At</th><td>{alert.triggered_at.isoformat()}</td></tr>
    </table>
    <p>Log in to the OTT Monitor dashboard to acknowledge this alert.</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.ALERT_FROM
    msg["To"] = settings.ALERT_TO
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.sendmail(settings.ALERT_FROM, settings.ALERT_TO, msg.as_string())
        logger.info(f"Email sent for alert {alert.id} ({channel_name})")
        return True
    except Exception as e:
        logger.error(f"Email send failed for alert {alert.id}: {e}")
        return False


def _severity_color(severity: ErrorSeverity) -> str:
    return {
        ErrorSeverity.CRITICAL: "#FF0000",
        ErrorSeverity.MAJOR: "#FFA500",
        ErrorSeverity.WARNING: "#800080",
        ErrorSeverity.INFO: "#0000FF",
    }.get(severity, "#888888")


async def dispatch_alert(alert: Alert, channel_name: str) -> None:
    """
    Fire all configured notification channels for an alert.
    Errors in one channel do not block the others.
    """
    import asyncio

    results = await asyncio.gather(
        send_webhook(alert, channel_name),
        asyncio.to_thread(send_email, alert, channel_name),
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Alert dispatch error: {r}")
