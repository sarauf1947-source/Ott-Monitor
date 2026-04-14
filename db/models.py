# -*- coding: utf-8 -*-
"""
OTT Monitor - SQLAlchemy ORM Models  (v2.2)
db/models.py

Tables:
  Original:  channels, metrics, errors, alerts
  v2.0:      users, system_settings, scheduled_reports, pinned_channels
  v2.2:      app_logs
"""

import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.database import Base


# =============================================================================
# Enums  (original - unchanged)
# =============================================================================

class ChannelStatus(str, PyEnum):
    UP      = "UP"
    DOWN    = "DOWN"
    ERROR   = "ERROR"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"


class ErrorSeverity(str, PyEnum):
    CRITICAL = "CRITICAL"
    MAJOR    = "MAJOR"
    WARNING  = "WARNING"
    INFO     = "INFO"


class ErrorType(str, PyEnum):
    STREAM_DOWN       = "STREAM_DOWN"
    BLACK_FRAME       = "BLACK_FRAME"
    VIDEO_JITTER      = "VIDEO_JITTER"
    VIDEO_FREEZE      = "VIDEO_FREEZE"
    AUDIO_SILENCE     = "AUDIO_SILENCE"
    AUDIO_JITTER      = "AUDIO_JITTER"
    LIP_SYNC_OUT      = "LIP_SYNC_OUT"
    HLS_SEGMENT_DELAY = "HLS_SEGMENT_DELAY"
    BITRATE_DROP      = "BITRATE_DROP"
    HIGH_LATENCY      = "HIGH_LATENCY"
    RESOLUTION_CHANGE = "RESOLUTION_CHANGE"


class AlertStatus(str, PyEnum):
    OPEN         = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED     = "RESOLVED"


class StreamProtocol(str, PyEnum):
    HLS   = "HLS"
    DASH  = "DASH"
    RTMP  = "RTMP"
    OTHER = "OTHER"


# =============================================================================
# Original models  (unchanged)
# =============================================================================

class Channel(Base):
    """Registered stream channel."""
    __tablename__ = "channels"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                = Column(String(255), nullable=False)
    stream_url          = Column(Text, nullable=False)
    protocol            = Column(Enum(StreamProtocol), default=StreamProtocol.HLS)
    group               = Column(String(100), nullable=True)
    description         = Column(Text, nullable=True)
    status              = Column(Enum(ChannelStatus), default=ChannelStatus.UNKNOWN, index=True)
    is_active           = Column(Boolean, default=True, index=True)
    expected_bitrate    = Column(Integer, nullable=True)
    expected_resolution = Column(String(20), nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    last_checked_at     = Column(DateTime(timezone=True), nullable=True)

    metrics = relationship("Metric", back_populates="channel", cascade="all, delete-orphan")
    errors  = relationship("Error",  back_populates="channel", cascade="all, delete-orphan")
    alerts  = relationship("Alert",  back_populates="channel", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("stream_url", name="uq_channels_stream_url"),
        Index("ix_channels_status_active", "status", "is_active"),
    )

    def __repr__(self):
        return f"<Channel {self.name!r} [{self.status}]>"


class Metric(Base):
    """Time-series metrics per channel (TimescaleDB hypertable on timestamp)."""
    __tablename__ = "metrics"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id        = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    timestamp         = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    bitrate           = Column(Integer, nullable=True)
    resolution_width  = Column(Integer, nullable=True)
    resolution_height = Column(Integer, nullable=True)
    fps               = Column(Float, nullable=True)
    codec_video       = Column(String(50), nullable=True)
    codec_audio       = Column(String(50), nullable=True)
    audio_level       = Column(Float, nullable=True)
    audio_sample_rate = Column(Integer, nullable=True)
    response_time     = Column(Integer, nullable=True)
    segment_duration  = Column(Float, nullable=True)
    video_jitter      = Column(Float, nullable=True)
    packet_loss       = Column(Float, nullable=True)
    is_available      = Column(Boolean, default=True)

    channel = relationship("Channel", back_populates="metrics")

    __table_args__ = (
        Index("ix_metrics_channel_timestamp", "channel_id", "timestamp"),
    )

    @property
    def resolution(self):
        if self.resolution_width and self.resolution_height:
            return f"{self.resolution_width}x{self.resolution_height}"
        return None


class Error(Base):
    """Detected stream errors (TimescaleDB hypertable on timestamp)."""
    __tablename__ = "errors"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id       = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    timestamp        = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    error_type       = Column(Enum(ErrorType), nullable=False)
    severity         = Column(Enum(ErrorSeverity), nullable=False)
    message          = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    resolved_at      = Column(DateTime(timezone=True), nullable=True)
    is_active        = Column(Boolean, default=True)

    channel = relationship("Channel", back_populates="errors")

    __table_args__ = (
        Index("ix_errors_channel_timestamp", "channel_id", "timestamp"),
        Index("ix_errors_type_severity",     "error_type", "severity"),
        Index("ix_errors_active",            "is_active"),
    )


class Alert(Base):
    """Active alerts generated from errors that exceed configured thresholds."""
    __tablename__ = "alerts"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id        = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    alert_type        = Column(Enum(ErrorType), nullable=False)
    severity          = Column(Enum(ErrorSeverity), nullable=False)
    status            = Column(Enum(AlertStatus), default=AlertStatus.OPEN, index=True)
    message           = Column(Text, nullable=True)
    triggered_at      = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at   = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by   = Column(String(100), nullable=True)
    resolved_at       = Column(DateTime(timezone=True), nullable=True)
    notification_sent = Column(Boolean, default=False)

    channel = relationship("Channel", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_status_severity", "status",     "severity"),
        Index("ix_alerts_channel_status",  "channel_id", "status"),
    )


# =============================================================================
# v2.0 models
# =============================================================================

class User(Base):
    """User accounts for JWT login and RBAC. Roles: admin, operator, viewer."""
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(String(64),  unique=True, nullable=False, index=True)
    email           = Column(String(255), unique=True, nullable=False)
    full_name       = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(String(16),  nullable=False, default="viewer")
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    last_login      = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User {self.username!r} role={self.role}>"


class SystemSettings(Base):
    """Key-value store for runtime configuration. category: smtp|webhook|alert|notification."""
    __tablename__ = "system_settings"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    category   = Column(String(64),  nullable=False, index=True)
    key        = Column(String(128), nullable=False)
    value      = Column(Text, nullable=True)
    is_secret  = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("category", "key", name="uq_settings_category_key"),
    )


class ScheduledReport(Base):
    """Scheduled report delivery jobs. channel_ids and email_recipients stored as JSON text."""
    __tablename__ = "scheduled_reports"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    name             = Column(String(255), nullable=False)
    report_type      = Column(String(64),  nullable=False, default="full")
    frequency        = Column(String(32),  nullable=False, default="weekly")
    channel_ids      = Column(Text, nullable=True)
    export_format    = Column(String(16),  default="pdf")
    email_recipients = Column(Text, nullable=True)
    webhook_url      = Column(String(500), nullable=True)
    is_active        = Column(Boolean, default=True)
    last_run_at      = Column(DateTime(timezone=True), nullable=True)
    next_run_at      = Column(DateTime(timezone=True), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    created_by       = Column(String(64), nullable=True)


class PinnedChannel(Base):
    """Per-user pinned channels at the top of the NOC dashboard."""
    __tablename__ = "pinned_channels"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, nullable=False, index=True)
    channel_id = Column(String(36), nullable=False)
    pinned_at  = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_pinned_user_channel"),
    )


# =============================================================================
# v2.2 new model
# =============================================================================

class AppLog(Base):
    """Structured application log entries written by the DB logging handler.
    Stored in PostgreSQL so they can be searched, filtered, and emailed.
    Retention is managed via the purge endpoint (default: 30 days).
    """
    __tablename__ = "app_logs"

    id        = Column(Integer,     primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    level     = Column(String(16),  nullable=False, index=True)
    logger    = Column(String(128), nullable=False, index=True)
    message   = Column(Text,        nullable=False)
    exception = Column(Text,        nullable=True)
    source    = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_app_logs_level_ts",   "level",  "timestamp"),
        Index("ix_app_logs_logger_ts",  "logger", "timestamp"),
    )

    def __repr__(self):
        return f"<AppLog {self.level} {self.logger}: {self.message[:40]}>"
