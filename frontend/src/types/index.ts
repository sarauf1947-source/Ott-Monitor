export type ChannelStatus = 'UP' | 'DOWN' | 'ERROR' | 'WARNING' | 'UNKNOWN'
export type ErrorSeverity = 'CRITICAL' | 'MAJOR' | 'WARNING' | 'INFO'
export type AlertStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'

export interface Channel {
  id: string; name: string; stream_url: string; protocol: string
  group: string | null; description: string | null; status: ChannelStatus
  is_active: boolean; expected_bitrate: number | null; expected_resolution: string | null
  created_at: string; updated_at: string | null; last_checked_at: string | null
}
export interface ChannelListResponse { total: number; page: number; per_page: number; items: Channel[] }

export interface Metric {
  id: string; channel_id: string; timestamp: string
  bitrate: number | null; resolution_width: number | null; resolution_height: number | null
  fps: number | null; codec_video: string | null; codec_audio: string | null
  audio_level: number | null; audio_sample_rate: number | null; response_time: number | null
  segment_duration: number | null; video_jitter: number | null; packet_loss: number | null; is_available: boolean
}
export interface MetricListResponse { channel_id: string; total: number; items: Metric[] }
export interface MetricSummary {
  channel_id: string; period: string; avg_bitrate: number | null; min_bitrate: number | null
  max_bitrate: number | null; avg_response_time: number | null; availability_pct: number | null; sample_count: number
}

export interface StreamError {
  id: string; channel_id: string; timestamp: string; error_type: string
  severity: ErrorSeverity; message: string | null; duration_seconds: number | null
  resolved_at: string | null; is_active: boolean
}
export interface StreamErrorListResponse { channel_id: string; total: number; items: StreamError[] }

export interface Alert {
  id: string; channel_id: string; alert_type: string; severity: ErrorSeverity
  channel_name?: string | null; channel_group?: string | null; channel_status?: ChannelStatus | null
  worker_shard?: number | null; worker_label?: string | null
  status: AlertStatus; message: string | null; triggered_at: string
  acknowledged_at: string | null; acknowledged_by: string | null; resolved_at: string | null; notification_sent: boolean
}
export interface AlertSummary {
  total: number; open: number; acknowledged: number; resolved: number
  critical: number; major: number; warning: number; info: number
}
export interface AlertListResponse { total: number; limit: number; offset: number; summary: AlertSummary; items: Alert[] }

export interface DashboardSummary {
  total_channels: number; active_channels: number; status_counts: Record<string, number>
  open_alerts: number; critical_alerts: number; warning_alerts: number; acknowledged_alerts: number; avg_bitrate_kbps: number | null
  avg_response_time_ms: number | null; availability_pct: number
  top_errors: Array<{ error_type: string; severity: string; count: number }>; recent_alerts: Alert[]; last_updated: string
}
export interface ChannelStatusSummary {
  id: string; name: string; status: ChannelStatus; group: string | null
  bitrate: number | null; resolution: string | null; fps: number | null
  audio_level: number | null; response_time: number | null
  last_error_type: string | null; last_checked_at: string | null; uptime_pct_24h: number | null
}
export interface HealthResponse { status: string; database: string; redis: string; version: string; uptime_seconds: number | null }

export interface WorkerMetric {
  worker_id: string; shard_id: number; streams_assigned: number; streams_ok: number
  streams_error: number; last_cycle_sec: number; last_updated: string
  notification_queue_depth: number; probe_concurrency: number
}
export interface SystemMetricsSnapshot {
  timestamp: string
  server: {
    cpu_percent: number
    cpu_count: number
    memory: { total_gb: number; used_gb: number; available_gb: number; percent: number }
    disk: { total_gb: number; used_gb: number; free_gb: number; percent: number }
    network: { bytes_sent_mb: number; bytes_recv_mb: number; bandwidth_sent_mbps: number; bandwidth_recv_mbps: number }
  }
  workers: {
    active_count: number; queue_depth: number; assigned_total: number; ok_total: number; error_total: number; details: WorkerMetric[]
  }
  redis: { connected: boolean }
}
export interface SystemMetricsHistoryPoint {
  timestamp: string
  cpu_percent: number
  memory_percent: number
  disk_percent: number
  bandwidth_sent_mbps: number
  bandwidth_recv_mbps: number
  workers_active: number
  workers_assigned: number
  workers_ok: number
  workers_error: number
  queue_depth: number
}
export interface SystemMetricsHistoryResponse {
  minutes: number
  points: SystemMetricsHistoryPoint[]
}
