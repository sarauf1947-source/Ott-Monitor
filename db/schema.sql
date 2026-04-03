-- ============================================================
-- OTT Monitor — PostgreSQL + TimescaleDB Schema
-- Run this after: CREATE DATABASE ott_monitor;
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ── Enums ──────────────────────────────────────────────────────────────────
CREATE TYPE channel_status   AS ENUM ('UP','DOWN','ERROR','WARNING','UNKNOWN');
CREATE TYPE error_severity   AS ENUM ('CRITICAL','MAJOR','WARNING','INFO');
CREATE TYPE error_type       AS ENUM (
    'STREAM_DOWN','BLACK_FRAME','VIDEO_JITTER',
    'VIDEO_FREEZE','AUDIO_SILENCE','AUDIO_JITTER',
    'LIP_SYNC_OUT','HLS_SEGMENT_DELAY','BITRATE_DROP',
    'HIGH_LATENCY','RESOLUTION_CHANGE'
);
CREATE TYPE alert_status     AS ENUM ('OPEN','ACKNOWLEDGED','RESOLVED');
CREATE TYPE stream_protocol  AS ENUM ('HLS','DASH','RTMP','OTHER');

-- ── channels ───────────────────────────────────────────────────────────────
CREATE TABLE channels (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255)      NOT NULL,
    stream_url          TEXT              NOT NULL UNIQUE,
    protocol            stream_protocol   NOT NULL DEFAULT 'HLS',
    "group"             VARCHAR(100),
    description         TEXT,
    status              channel_status    NOT NULL DEFAULT 'UNKNOWN',
    is_active           BOOLEAN           NOT NULL DEFAULT TRUE,
    expected_bitrate    INTEGER,
    expected_resolution VARCHAR(20),
    created_at          TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    last_checked_at     TIMESTAMPTZ
);

CREATE INDEX ix_channels_status_active ON channels (status, is_active);
CREATE INDEX ix_channels_name          ON channels (name);

-- ── metrics (TimescaleDB hypertable) ──────────────────────────────────────
CREATE TABLE metrics (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid(),
    channel_id          UUID        NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    bitrate             INTEGER,
    resolution_width    INTEGER,
    resolution_height   INTEGER,
    fps                 FLOAT,
    codec_video         VARCHAR(50),
    codec_audio         VARCHAR(50),
    audio_level         FLOAT,
    audio_sample_rate   INTEGER,
    response_time       INTEGER,
    segment_duration    FLOAT,
    video_jitter        FLOAT,
    packet_loss         FLOAT,
    is_available        BOOLEAN     NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id, timestamp)
);

-- Convert to hypertable (partitioned by day)
SELECT create_hypertable('metrics', 'timestamp',
    chunk_time_interval => INTERVAL '1 day');

-- Indexes
CREATE INDEX ix_metrics_channel_timestamp ON metrics (channel_id, timestamp DESC);

-- Compression: compress chunks older than 7 days (~90% space saving)
ALTER TABLE metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'channel_id'
);
SELECT add_compression_policy('metrics', INTERVAL '7 days');

-- Retention: auto-drop data older than 90 days
SELECT add_retention_policy('metrics', INTERVAL '90 days');

-- ── errors (TimescaleDB hypertable) ───────────────────────────────────────
CREATE TABLE errors (
    id               UUID        NOT NULL DEFAULT gen_random_uuid(),
    channel_id       UUID        NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_type       error_type  NOT NULL,
    severity         error_severity NOT NULL,
    message          TEXT,
    duration_seconds INTEGER,
    resolved_at      TIMESTAMPTZ,
    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('errors', 'timestamp',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX ix_errors_channel_timestamp ON errors (channel_id, timestamp DESC);
CREATE INDEX ix_errors_type_severity     ON errors (error_type, severity);
CREATE INDEX ix_errors_active            ON errors (is_active) WHERE is_active = TRUE;

-- Retention: keep errors for 180 days
SELECT add_retention_policy('errors', INTERVAL '180 days');

-- ── alerts ─────────────────────────────────────────────────────────────────
CREATE TABLE alerts (
    id                 UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id         UUID           NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    alert_type         error_type     NOT NULL,
    severity           error_severity NOT NULL,
    status             alert_status   NOT NULL DEFAULT 'OPEN',
    message            TEXT,
    triggered_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    acknowledged_at    TIMESTAMPTZ,
    acknowledged_by    VARCHAR(100),
    resolved_at        TIMESTAMPTZ,
    notification_sent  BOOLEAN        NOT NULL DEFAULT FALSE
);

CREATE INDEX ix_alerts_status_severity  ON alerts (status, severity);
CREATE INDEX ix_alerts_channel_status   ON alerts (channel_id, status);
CREATE INDEX ix_alerts_triggered_at     ON alerts (triggered_at DESC);

-- ── Trigger: update channels.updated_at on every row change ──────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_channels_updated_at
    BEFORE UPDATE ON channels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Useful views ───────────────────────────────────────────────────────────

-- NOC summary view
CREATE VIEW v_noc_summary AS
SELECT
    COUNT(*)                                           AS total_channels,
    COUNT(*) FILTER (WHERE status = 'UP')              AS up,
    COUNT(*) FILTER (WHERE status = 'DOWN')            AS down,
    COUNT(*) FILTER (WHERE status = 'ERROR')           AS error,
    COUNT(*) FILTER (WHERE status = 'WARNING')         AS warning,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'UP')::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 2
    )                                                  AS availability_pct
FROM channels
WHERE is_active = TRUE;

-- Latest metric per channel
CREATE VIEW v_channel_latest_metric AS
SELECT DISTINCT ON (channel_id)
    channel_id,
    timestamp,
    bitrate,
    resolution_width,
    resolution_height,
    fps,
    codec_video,
    codec_audio,
    audio_level,
    response_time,
    is_available
FROM metrics
ORDER BY channel_id, timestamp DESC;
