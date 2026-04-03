"""
Channels CRUD endpoints.
GET /channels, POST /channels, GET /channels/{id}, PATCH /channels/{id}, DELETE /channels/{id}
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Channel, ChannelStatus
from db.schemas import ChannelCreate, ChannelListResponse, ChannelResponse, ChannelUpdate
from utils.cache import CacheKeys, cache_delete, cache_get, cache_set
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/channels", response_model=ChannelListResponse)
async def list_channels(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: Optional[ChannelStatus] = None,
    group: Optional[str] = None,
    is_active: Optional[bool] = True,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List channels with optional filtering and pagination."""
    query = select(Channel)

    if status:
        query = query.where(Channel.status == status)
    if group:
        query = query.where(Channel.group == group)
    if is_active is not None:
        query = query.where(Channel.is_active == is_active)
    if search:
        query = query.where(Channel.name.ilike(f"%{search}%"))

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginate
    query = query.order_by(Channel.name).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    channels = result.scalars().all()

    return ChannelListResponse(
        total=total,
        page=page,
        per_page=per_page,
        items=[ChannelResponse.model_validate(ch) for ch in channels],
    )


@router.post("/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(payload: ChannelCreate, db: AsyncSession = Depends(get_db)):
    """Register a new stream channel."""
    channel = Channel(**payload.model_dump())
    db.add(channel)
    await db.flush()
    await db.refresh(channel)
    await cache_delete(CacheKeys.CHANNEL_LIST)
    logger.info(f"Channel created: {channel.name} ({channel.id})")
    return ChannelResponse.model_validate(channel)


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single channel by ID."""
    channel = await _get_or_404(db, channel_id)
    return ChannelResponse.model_validate(channel)


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: uuid.UUID,
    payload: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partially update a channel."""
    channel = await _get_or_404(db, channel_id)

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(channel, field, value)

    await db.flush()
    await db.refresh(channel)
    await cache_delete(CacheKeys.channel_status(str(channel_id)))
    logger.info(f"Channel updated: {channel.name} ({channel_id})")
    return ChannelResponse.model_validate(channel)


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(channel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a channel and all associated data."""
    channel = await _get_or_404(db, channel_id)
    await db.delete(channel)
    await cache_delete(CacheKeys.channel_status(str(channel_id)))
    logger.info(f"Channel deleted: {channel.name} ({channel_id})")


async def _get_or_404(db: AsyncSession, channel_id: uuid.UUID) -> Channel:
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return channel
