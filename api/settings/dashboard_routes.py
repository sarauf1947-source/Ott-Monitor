# -*- coding: utf-8 -*-
"""Pinned channels per user. api/settings/dashboard_routes.py"""
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.auth_deps import get_current_user
from db.database import get_db

dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard Pins"])


class PinRequest(BaseModel):
    channel_ids: List[str]  # UUID strings


@dashboard_router.get("/pinned")
async def get_pinned(db: AsyncSession = Depends(get_db), cu=Depends(get_current_user)):
    from db.models import PinnedChannel, Channel
    import uuid as _uuid
    pins = await db.execute(
        select(PinnedChannel.channel_id)
        .where(PinnedChannel.user_id == cu.id)
        .order_by(PinnedChannel.pinned_at)
    )
    channel_ids = [r[0] for r in pins.fetchall()]
    channels = []
    for cid_str in channel_ids:
        try:
            cid = _uuid.UUID(cid_str)
        except ValueError:
            continue
        ch = (await db.execute(select(Channel).where(Channel.id == cid))).scalar_one_or_none()
        if ch:
            channels.append({
                "id":         str(ch.id),
                "name":       ch.name,
                "stream_url": ch.stream_url,
                "status":     ch.status.value if hasattr(ch.status, "value") else str(ch.status),
            })
    return {"pinned": channels}


@dashboard_router.post("/pinned")
async def set_pinned(req: PinRequest, db: AsyncSession = Depends(get_db), cu=Depends(get_current_user)):
    from db.models import PinnedChannel
    await db.execute(delete(PinnedChannel).where(PinnedChannel.user_id == cu.id))
    for cid in req.channel_ids:
        db.add(PinnedChannel(user_id=cu.id, channel_id=str(cid)))
    await db.flush()
    return {"message": f"{len(req.channel_ids)} channel(s) pinned"}


@dashboard_router.delete("/pinned/{channel_id}")
async def unpin(channel_id: str, db: AsyncSession = Depends(get_db), cu=Depends(get_current_user)):
    from db.models import PinnedChannel
    await db.execute(
        delete(PinnedChannel).where(
            PinnedChannel.user_id   == cu.id,
            PinnedChannel.channel_id == channel_id,
        )
    )
    await db.flush()
    return {"message": "Channel unpinned"}
