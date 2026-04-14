# -*- coding: utf-8 -*-
"""Settings API - SMTP, webhooks, alert thresholds, notifications. api/settings/settings_routes.py"""
import json
import smtplib
import uuid as _uuid
from email.mime.text import MIMEText
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.auth_deps import get_current_user, require_admin
from db.database import get_db
from utils.alerts import send_test_webhook

settings_router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])
MASKED = "........"


async def _get(db: AsyncSession, category: str, key: str) -> Optional[str]:
    from db.models import SystemSettings
    result = await db.execute(
        select(SystemSettings).where(
            SystemSettings.category == category,
            SystemSettings.key == key,
        )
    )
    row = result.scalar_one_or_none()
    return row.value if row else None


async def _set(db: AsyncSession, category: str, key: str, value: str,
               is_secret: bool = False, updated_by: str = "system") -> None:
    from db.models import SystemSettings
    result = await db.execute(
        select(SystemSettings).where(
            SystemSettings.category == category,
            SystemSettings.key == key,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.value      = value
        row.updated_by = updated_by
    else:
        db.add(SystemSettings(category=category, key=key, value=value,
                              is_secret=is_secret, updated_by=updated_by))
    await db.flush()


# Schemas
class SMTPConfig(BaseModel):
    host:       str
    port:       int = 587
    username:   str
    password:   Optional[str] = None
    use_tls:    bool = True
    from_email: str
    from_name:  str = "OTT Monitor"


class WebhookEntry(BaseModel):
    name:        str
    url:         str
    retry_count: int = 3
    is_active:   bool = True


class AlertConfig(BaseModel):
    stream_down_enabled:         bool = True
    audio_silence_threshold_sec: int  = 60
    bitrate_drop_percent:        int  = 30
    enable_email:                bool = True
    enable_webhook:              bool = True
    severity_email_min:          str  = "major"


class NotificationConfig(BaseModel):
    popup_enabled: bool = True
    sound_enabled: bool = False
    sound_volume:  int  = 50


class TestEmailRequest(BaseModel):
    to_email: str


class TestWebhookRequest(BaseModel):
    url: Optional[str] = None
    name: Optional[str] = "Test Webhook"
    webhook_id: Optional[str] = None


# SMTP
@settings_router.get("/smtp")
async def get_smtp(db: AsyncSession = Depends(get_db), _u=Depends(get_current_user)):
    return {
        "host":       await _get(db, "smtp", "host")       or "",
        "port":       int(await _get(db, "smtp", "port")   or 587),
        "username":   await _get(db, "smtp", "username")   or "",
        "password":   MASKED if await _get(db, "smtp", "password") else "",
        "use_tls":    (await _get(db, "smtp", "use_tls")   or "true") == "true",
        "from_email": await _get(db, "smtp", "from_email") or "",
        "from_name":  await _get(db, "smtp", "from_name")  or "OTT Monitor",
    }


@settings_router.put("/smtp")
async def save_smtp(cfg: SMTPConfig, db: AsyncSession = Depends(get_db), cu=Depends(require_admin)):
    u = cu.username
    await _set(db, "smtp", "host",       cfg.host,               updated_by=u)
    await _set(db, "smtp", "port",       str(cfg.port),          updated_by=u)
    await _set(db, "smtp", "username",   cfg.username,           updated_by=u)
    await _set(db, "smtp", "use_tls",    str(cfg.use_tls).lower(), updated_by=u)
    await _set(db, "smtp", "from_email", cfg.from_email,         updated_by=u)
    await _set(db, "smtp", "from_name",  cfg.from_name,          updated_by=u)
    if cfg.password and cfg.password != MASKED:
        await _set(db, "smtp", "password", cfg.password, is_secret=True, updated_by=u)
    return {"message": "SMTP settings saved"}


@settings_router.post("/smtp/test")
async def test_smtp(req: TestEmailRequest, db: AsyncSession = Depends(get_db), _u=Depends(require_admin)):
    host = await _get(db, "smtp", "host")
    if not host:
        raise HTTPException(status_code=400, detail="SMTP not configured")
    port      = int(await _get(db, "smtp", "port") or 587)
    username  = await _get(db, "smtp", "username")
    password  = await _get(db, "smtp", "password")
    from_email = await _get(db, "smtp", "from_email") or username
    use_tls   = (await _get(db, "smtp", "use_tls") or "true") == "true"
    try:
        msg = MIMEText("Test email from OTT Monitor.")
        msg["Subject"] = "OTT Monitor - SMTP Test"
        msg["From"]    = from_email
        msg["To"]      = req.to_email
        with smtplib.SMTP(host, port, timeout=10) as s:
            if use_tls:
                s.starttls()
            if username and password:
                s.login(username, password)
            s.sendmail(from_email, [req.to_email], msg.as_string())
        return {"message": "Test email sent"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SMTP error: {exc}")


# Webhooks
@settings_router.get("/webhooks")
async def get_webhooks(db: AsyncSession = Depends(get_db), _u=Depends(get_current_user)):
    raw = await _get(db, "webhook", "list")
    return {"webhooks": json.loads(raw) if raw else []}


@settings_router.post("/webhooks")
async def add_webhook(cfg: WebhookEntry, db: AsyncSession = Depends(get_db), cu=Depends(require_admin)):
    raw   = await _get(db, "webhook", "list")
    hooks = json.loads(raw) if raw else []
    hooks.append({**cfg.model_dump(), "id": str(_uuid.uuid4())})
    await _set(db, "webhook", "list", json.dumps(hooks), updated_by=cu.username)
    return {"message": "Webhook added", "webhooks": hooks}


@settings_router.delete("/webhooks/{webhook_id}")
async def remove_webhook(webhook_id: str, db: AsyncSession = Depends(get_db), cu=Depends(require_admin)):
    raw   = await _get(db, "webhook", "list")
    hooks = [h for h in (json.loads(raw) if raw else []) if h.get("id") != webhook_id]
    await _set(db, "webhook", "list", json.dumps(hooks), updated_by=cu.username)
    return {"message": "Webhook removed"}


@settings_router.post("/webhooks/test")
async def test_webhook(req: TestWebhookRequest, db: AsyncSession = Depends(get_db), _u=Depends(require_admin)):
    target_url = (req.url or "").strip()
    target_name = (req.name or "Test Webhook").strip() or "Test Webhook"

    if req.webhook_id:
        raw = await _get(db, "webhook", "list")
        hooks = json.loads(raw) if raw else []
        selected = next((h for h in hooks if h.get("id") == req.webhook_id), None)
        if not selected:
            raise HTTPException(status_code=404, detail="Webhook not found")
        target_url = str(selected.get("url", "")).strip()
        target_name = str(selected.get("name", target_name)).strip() or target_name

    if not target_url:
        raise HTTPException(status_code=400, detail="Webhook URL is required")

    try:
        await send_test_webhook(target_url, target_name)
        return {"message": f"Test webhook sent to {target_name}"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Webhook error: {exc}")


# Alerts
@settings_router.get("/alerts")
async def get_alerts(db: AsyncSession = Depends(get_db), _u=Depends(get_current_user)):
    raw = await _get(db, "alert", "config")
    return json.loads(raw) if raw else AlertConfig().model_dump()


@settings_router.put("/alerts")
async def save_alerts(cfg: AlertConfig, db: AsyncSession = Depends(get_db), cu=Depends(require_admin)):
    await _set(db, "alert", "config", json.dumps(cfg.model_dump()), updated_by=cu.username)
    return {"message": "Alert config saved"}


# Notifications
@settings_router.get("/notifications")
async def get_notifications(db: AsyncSession = Depends(get_db), _u=Depends(get_current_user)):
    raw = await _get(db, "notification", "config")
    return json.loads(raw) if raw else NotificationConfig().model_dump()


@settings_router.put("/notifications")
async def save_notifications(cfg: NotificationConfig, db: AsyncSession = Depends(get_db), cu=Depends(get_current_user)):
    await _set(db, "notification", "config", json.dumps(cfg.model_dump()), updated_by=cu.username)
    return {"message": "Notification settings saved"}
