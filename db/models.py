"""
OTT Monitor - SQLAlchemy ORM Models
Defines all database tables including TimescaleDB hypertables.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Enum, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.database import Base


# ── Enums ──────────────────────────────────────────────────────────────────────

class ChannelStatus(str, PyEnum):
    UP = "UP"
    DOWN = "DOWN"
    ERROR = "ERROR"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"


class ErrorSeverity(str, PyEnum):
    CRITICAL = "CRITICAL"    # Red
    MAJOR = "MAJOR"          # Yellow
    WARNING = "WARNING"      # Purple
    INFO = "INFO"            # Blue


class ErrorType(str, PyEnum):
    # Critical (RED)
    STREAM_DOWN = "STREAM_DOWN"
    BLACK_FRAME = "BLACK_FRAME"
    VIDEO_JITTER = "VIDEO_JITTER"
    # Major (YELLOW)
    VIDEO_FREEZE = "VIDEO_FREEZE"
    AUDIO_SILENCE = "AUDIO_SILENCE"
    AUDIO_JITTER = "AUDIO_JITTER"
    # Warning (PURPLE)
    LIP_SYNC_OUT = "LIP_SYNC_OUT"
    HLS_SEGMENT_DELAY = "HLS_SEGMENT_DELAY"
    BITRATE_DROP = "BITRATE_DROP"
    # Info
    HIGH_LATENCY = "HIGH_LATENCY"
    RESOLUTION_CHANGE = "RESOLUTION_CHANGE"


class AlertStatus(str, PyEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class StreamProtocol(str, PyEnum):
    HLS = "HLS"
    DASH = "DASH"
    RTMP = "RTMP"
    OTHER = "OTHER"


# ── Models ─────────────────────────────────────────────────────────────────────

class Channel(Base):
    """Registered stream channel."""
    __tablename__ = "channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    stream_url = Column(Text, nullable=False)
    protocol = Column(Enum(StreamProtocol), default=StreamProtocol.HLS)
    group = Column(String(100), nullable=True)        # e.g., "Sports", "News"
    description = Column(Text, nullable=True)
    status = Column(Enum(ChannelStatus), default=ChannelStatus.UNKNOWN, index=True)
    is_active = Column(Boolean, default=True, index=True)
    expected_bitrate = Column(Integer, nullable=True)  # kbps
    expected_resolution = Column(String(20), nullable=True)  # e.g., "1920x1080"

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    last_checked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    metrics = relationship("Metric", back_populates="channel", cascade="all, delete-orphan")
    errors = relationship("Error", back_populates="channel", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="channel", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("stream_url", name="uq_channels_stream_url"),
        Index("ix_channels_status_active", "status", "is_active"),
    )

    def __repr__(self):
        return f"<Channel {self.name!r} [{self.status}]>"


class Metric(Base):
    """
    Time-series metrics per channel.
    This table is converted to a TimescaleDB hypertable on 'timestamp'.
    """
    __tablename__ = "metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    # Stream quality metrics
    bitrate = Column(Integer, nullable=True)           # kbps
    resolution_width = Column(Integer, nullable=True)
    resolution_height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    codec_video = Column(String(50), nullable=True)    # e.g., "h264"
    codec_audio = Column(String(50), nullable=True)    # e.g., "aac"

    # Audio metrics
    audio_level = Column(Float, nullable=True)         # dBFS
    audio_sample_rate = Column(Integer, nullable=True) # Hz

    # Network/timing metrics
    response_time = Column(Integer, nullable=True)     # ms
    segment_duration = Column(Float, nullable=True)    # seconds (HLS)

    # Derived quality signals
    video_jitter = Column(Float, nullable=True)        # ms
    packet_loss = Column(Float, nullable=True)         # percentage
    is_available = Column(Boolean, default=True)

    channel = relationship("Channel", back_populates="metrics")

    __table_args__ = (
        Index("ix_metrics_channel_timestamp", "channel_id", "timestamp"),
    )

    @property
    def resolution(self) -> str | None:
        if self.resolution_width and self.resolution_height:
            return f"{self.resolution_width}x{self.resolution_height}"
        return None


class Error(Base):
    """
    Detected stream errors and anomalies.
    Also converted to a TimescaleDB hypertable for efficient time-range queries.
    """
    __tablename__ = "errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    error_type = Column(Enum(ErrorType), nullable=False)
    severity = Column(Enum(ErrorSeverity), nullable=False)
    message = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # how long error lasted
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    channel = relationship("Channel", back_populates="errors")

    __table_args__ = (
        Index("ix_errors_channel_timestamp", "channel_id", "timestamp"),
        Index("ix_errors_type_severity", "error_type", "severity"),
        Index("ix_errors_active", "is_active"),
    )


class Alert(Base):
    """Active alerts — generated from detected errors that exceed thresholds."""
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)

    alert_type = Column(Enum(ErrorType), nullable=False)
    severity = Column(Enum(ErrorSeverity), nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.OPEN, index=True)
    message = Column(Text, nullable=True)

    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    notification_sent = Column(Boolean, default=False)

    channel = relationship("Channel", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_channel_status", "channel_id", "status"),
    )
