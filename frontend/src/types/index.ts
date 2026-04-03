export type ChannelStatus = 'UP' | 'DOWN' | 'ERROR' | 'WARNING' | 'UNKNOWN'
export type ErrorSeverity = 'CRITICAL' | 'MAJOR' | 'WARNING' | 'INFO'
export type AlertStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'
export type StreamProtocol = 'HLS' | 'DASH' | 'RTMP' | 'OTHER'

export interface Channel {
  id: string
  name: string
  stream_url: string
  protocol: StreamProtocol
  group: string | null
  description: string | null
  status: ChannelStatus
  is_active: boolean
  expected_bitrate: number | null
  expected_resolution: string | null
  created_at: string
  updated_at: string | null
  last_checked_at: string | null
}

export interface ChannelListResponse {
  total: number
  page: number
  per_page: number
  items: Channel[]
}

export interface Metric {
  id: string
  channel_id: string
  timestamp: string
  bitrate: number | null
  resolution_width: number | null
  resolution_height: number | null
  fps: number | null
  codec_video: string | null
  codec_audio: string | null
  audio_level: number | null
  audio_sample_rate: number | null
  response_time: number | null
  segment_duration: number | null
  video_jitter: number | null
  packet_loss: number | null
  is_available: boolean
  resolution: string | null
}

export interface MetricListResponse {
  channel_id: string
  total: number
  items: Metric[]
}

export interface MetricSummary {
  channel_id: string
  period: string
  avg_bitrate: number | null
  min_bitrate: number | null
  max_bitrate: number | null
  avg_response_time: number | null
  availability_pct: number | null
  sample_count: number
}

export interface StreamError {
  id: string
  channel_id: string
  timestamp: string
  error_type: string
  severity: ErrorSeverity
  message: string | null
  duration_seconds: number | null
  resolved_at: string | null
  is_active: boolean
}

export interface StreamErrorListResponse {
  total: number
  items: StreamError[]
}

export interface Alert {
  id: string
  channel_id: string
  alert_type: string
  severity: ErrorSeverity
  status: AlertStatus
  message: string | null
  triggered_at: string
  acknowledged_at: string | null
  acknowledged_by: string | null
  resolved_at: string | null
  notification_sent: boolean
}

export interface AlertListResponse {
  total: number
  items: Alert[]
}

export interface DashboardSummary {
  total_channels: number
  active_channels: number
  status_counts: Record<string, number>
  open_alerts: number
  critical_alerts: number
  avg_bitrate_kbps: number | null
  avg_response_time_ms: number | null
  availability_pct: number
  top_errors: Array<{ error_type: string; severity: string; count: number }>
  last_updated: string
}

export interface ChannelStatusSummary {
  id: string
  name: string
  status: ChannelStatus
  group: string | null
  bitrate: number | null
  resolution: string | null
  fps: number | null
  audio_level: number | null
  response_time: number | null
  last_error_type: string | null
  last_checked_at: string | null
  uptime_pct_24h: number | null
}

export interface HealthResponse {
  status: string
  database: string
  redis: string
  version: string
  uptime_seconds: number | null
}
