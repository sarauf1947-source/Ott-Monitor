"""
OTT Monitor - Pydantic Schemas
Request/response models for all API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl

from db.models import AlertStatus, ChannelStatus, ErrorSeverity, ErrorType, StreamProtocol


# ── Base Helpers ───────────────────────────────────────────────────────────────

class OrmBase(BaseModel):
    model_config = {"from_attributes": True}


# ── Channel Schemas ────────────────────────────────────────────────────────────

class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    stream_url: str = Field(..., description="Full HLS/DASH stream URL")
    protocol: StreamProtocol = StreamProtocol.HLS
    group: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    expected_bitrate: Optional[int] = Field(None, ge=0, description="Expected bitrate in kbps")
    expected_resolution: Optional[str] = None


class ChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    stream_url: Optional[str] = None
    protocol: Optional[StreamProtocol] = None
    group: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    expected_bitrate: Optional[int] = None
    expected_resolution: Optional[str] = None


class ChannelResponse(OrmBase):
    id: uuid.UUID
    name: str
    stream_url: str
    protocol: StreamProtocol
    group: Optional[str]
    description: Optional[str]
    status: ChannelStatus
    is_active: bool
    expected_bitrate: Optional[int]
    expected_resolution: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    last_checked_at: Optional[datetime]


class ChannelListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: List[ChannelResponse]


# ── Metric Schemas ─────────────────────────────────────────────────────────────

class MetricResponse(OrmBase):
    id: uuid.UUID
    channel_id: uuid.UUID
    timestamp: datetime
    bitrate: Optional[int]
    resolution_width: Optional[int]
    resolution_height: Optional[int]
    fps: Optional[float]
    codec_video: Optional[str]
    codec_audio: Optional[str]
    audio_level: Optional[float]
    audio_sample_rate: Optional[int]
    response_time: Optional[int]
    segment_duration: Optional[float]
    video_jitter: Optional[float]
    packet_loss: Optional[float]
    is_available: bool
    resolution: Optional[str] = None

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        instance = super().model_validate(obj, *args, **kwargs)
        if instance.resolution_width and instance.resolution_height:
            instance.resolution = f"{instance.resolution_width}x{instance.resolution_height}"
        return instance


class MetricListResponse(BaseModel):
    channel_id: uuid.UUID
    total: int
    items: List[MetricResponse]


class MetricSummary(BaseModel):
    """Aggregated metric stats for a time window."""
    channel_id: uuid.UUID
    period: str
    avg_bitrate: Optional[float]
    min_bitrate: Optional[float]
    max_bitrate: Optional[float]
    avg_response_time: Optional[float]
    availability_pct: Optional[float]
    sample_count: int


# ── Error Schemas ──────────────────────────────────────────────────────────────

class ErrorResponse(OrmBase):
    id: uuid.UUID
    channel_id: uuid.UUID
    timestamp: datetime
    error_type: ErrorType
    severity: ErrorSeverity
    message: Optional[str]
    duration_seconds: Optional[int]
    resolved_at: Optional[datetime]
    is_active: bool


class ErrorListResponse(BaseModel):
    channel_id: uuid.UUID
    total: int
    items: List[ErrorResponse]


# ── Alert Schemas ──────────────────────────────────────────────────────────────

class AlertResponse(OrmBase):
    id: uuid.UUID
    channel_id: uuid.UUID
    alert_type: ErrorType
    severity: ErrorSeverity
    status: AlertStatus
    message: Optional[str]
    triggered_at: datetime
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    resolved_at: Optional[datetime]
    notification_sent: bool


class AlertAcknowledge(BaseModel):
    acknowledged_by: str = Field(..., min_length=1)


class AlertListResponse(BaseModel):
    total: int
    items: List[AlertResponse]


# ── Dashboard Schemas ──────────────────────────────────────────────────────────

class StatusCount(BaseModel):
    status: ChannelStatus
    count: int


class DashboardSummary(BaseModel):
    """Top-level NOC dashboard summary."""
    total_channels: int
    active_channels: int
    status_counts: Dict[str, int]
    open_alerts: int
    critical_alerts: int
    avg_bitrate_kbps: Optional[float]
    avg_response_time_ms: Optional[float]
    availability_pct: float
    top_errors: List[Dict[str, Any]]
    last_updated: datetime


class ChannelStatusSummary(BaseModel):
    """Per-channel status card for the NOC grid."""
    id: uuid.UUID
    name: str
    status: ChannelStatus
    group: Optional[str]
    bitrate: Optional[int]
    resolution: Optional[str]
    fps: Optional[float]
    audio_level: Optional[float]
    response_time: Optional[int]
    last_error_type: Optional[str]
    last_checked_at: Optional[datetime]
    uptime_pct_24h: Optional[float]


# ── Report Schemas ─────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    channel_ids: Optional[List[uuid.UUID]] = None   # None = all channels
    start_time: datetime
    end_time: datetime
    format: str = Field("json", pattern="^(json|csv|pdf)$")
    include_metrics: bool = True
    include_errors: bool = True


class ReportResponse(BaseModel):
    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    channel_count: int
    data: Optional[List[Dict[str, Any]]] = None
    download_url: Optional[str] = None


# ── Health Schemas ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    version: str = "1.0.0"
    uptime_seconds: Optional[float] = None
