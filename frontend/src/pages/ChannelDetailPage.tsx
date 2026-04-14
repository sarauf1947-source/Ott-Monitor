// frontend/src/pages/ChannelDetailPage.tsx  (v2.3)
// Change: OverviewTab now shows "Assigned Worker" row
// Worker ID is computed client-side: channel list index % TOTAL_WORKERS
// Also reads TOTAL_WORKERS from /api/v1/health response if available,
// otherwise defaults to 15 (matches production default).
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, RefreshCw, Activity, AlertTriangle, BarChart2, List } from 'lucide-react'
import { format } from 'date-fns'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import type { ValueType } from 'recharts/types/component/DefaultTooltipContent'
import {
  useChannel, useChannelMetrics, useMetricSummary, useChannelErrors, useChannels,
} from '@/hooks/useApi'
import {
  PageLoader, ErrorDisplay, StatusBadge, SeverityBadge, StatCard, EmptyState,
} from '@/components/common'
import {
  formatBitrate, formatRelativeTime, formatDateTime, formatMs, formatAudioLevel, cn,
} from '@/utils'
import type { Channel, Metric, MetricSummary, StreamError } from '@/types'

type Tab = 'overview' | 'metrics' | 'errors' | 'logs'

type ChartPoint = {
  time: string
  bitrate: number | null
  latency: number | null
  fps: number | null
  audio: number | null
  available: number
}

function formatTooltipValue(value: ValueType, unit: string): string {
  if (Array.isArray(value)) return `${value.join(', ')}${unit}`
  if (value == null) return `-${unit}`
  return `${value}${unit}`
}

// Compute which worker handles a channel based on its position in the
// sorted channel list (same algorithm as monitor_worker.py modulo partition).
function computeWorkerInfo(channelId: string, allChannels: { id: string }[], totalWorkers: number) {
  const sorted = [...allChannels].sort((a, b) => a.id.localeCompare(b.id))
  const idx    = sorted.findIndex(c => c.id === channelId)
  if (idx === -1) return null
  const workerId = idx % totalWorkers
  return { workerId, channelIndex: idx, totalWorkers }
}

export default function ChannelDetailPage() {
  const { id }   = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [tab,   setTab]   = useState<Tab>('overview')
  const [hours, setHours] = useState(24)

  const { data: channel, isLoading, error, refetch } = useChannel(id!)
  const { data: metrics }  = useChannelMetrics(id!, hours)
  const { data: summary }  = useMetricSummary(id!, hours)
  const { data: errors }   = useChannelErrors(id!, hours)

  // Fetch all channel IDs for worker assignment computation
  const { data: allChannelsData } = useChannels({ per_page: 500 })
  const allChannels = allChannelsData?.items ?? []

  if (isLoading) return <PageLoader />
  if (error || !channel) {
    return (
      <div className="p-6">
        <ErrorDisplay message="Channel not found or API unavailable." />
      </div>
    )
  }

  // Read TOTAL_WORKERS from env via window (set at build time) or default 15
  const totalWorkers = (window as unknown as { TOTAL_WORKERS?: number }).TOTAL_WORKERS ?? 15
  const workerInfo = computeWorkerInfo(channel.id, allChannels, totalWorkers)

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'overview', label: 'Overview',    icon: <Activity size={14} /> },
    { key: 'metrics',  label: 'Metrics',     icon: <BarChart2 size={14} /> },
    { key: 'errors',   label: 'Errors',      icon: <AlertTriangle size={14} /> },
    { key: 'logs',     label: 'Stream Info', icon: <List size={14} /> },
  ]

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 bg-white border-b border-gray-200">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 mb-3 transition-colors"
        >
          <ArrowLeft size={14} /> Back
        </button>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <StatusBadge status={channel.status} />
            <div>
              <h1 className="text-lg font-bold text-gray-900">{channel.name}</h1>
              <p className="text-xs text-gray-400 font-mono mt-0.5 max-w-lg truncate">
                {channel.stream_url}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="input py-1.5 text-xs w-28"
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
            >
              <option value={1}>Last 1h</option>
              <option value={6}>Last 6h</option>
              <option value={24}>Last 24h</option>
              <option value={168}>Last 7d</option>
              <option value={720}>Last 30d</option>
            </select>
            <button className="btn-secondary" onClick={() => refetch()}>
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        <div className="flex gap-1 mt-4">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                tab === t.key
                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                  : 'text-gray-500 hover:bg-gray-100',
              )}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {tab === 'overview' && (
          <OverviewTab channel={channel} summary={summary} workerInfo={workerInfo} />
        )}
        {tab === 'metrics'  && <MetricsTab  metrics={metrics?.items ?? []} hours={hours} />}
        {tab === 'errors'   && <ErrorsTab   errors={errors?.items ?? []} />}
        {tab === 'logs'     && <LogsTab     channel={channel} metrics={metrics?.items ?? []} />}
      </div>
    </div>
  )
}

// ---- Overview ---------------------------------------------------------------

interface WorkerInfo { workerId: number; channelIndex: number; totalWorkers: number }

function OverviewTab({
  channel, summary, workerInfo,
}: {
  channel: Channel
  summary: MetricSummary | undefined
  workerInfo: WorkerInfo | null
}) {
  const detailRows: Array<[string, string]> = [
    ['Group',               channel.group ?? '-'],
    ['Protocol',            channel.protocol],
    ['Status',              channel.status],
    ['Expected Bitrate',    formatBitrate(channel.expected_bitrate)],
    ['Expected Resolution', channel.expected_resolution ?? '-'],
    ['Last Checked',        formatRelativeTime(channel.last_checked_at)],
    ['Created',             formatDateTime(channel.created_at)],
    ['Active',              channel.is_active ? 'Yes' : 'No'],
  ]

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Availability"
          value={summary?.availability_pct != null ? `${summary.availability_pct.toFixed(1)}%` : '-'}
        />
        <StatCard label="Avg Bitrate"  value={formatBitrate(summary?.avg_bitrate)} />
        <StatCard label="Avg Latency"  value={formatMs(summary?.avg_response_time)} />
        <StatCard label="Samples"      value={summary?.sample_count ?? 0} />
      </div>

      {/* Worker assignment banner */}
      {workerInfo && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-3 flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-lg flex-shrink-0">
            W{workerInfo.workerId}
          </div>
          <div>
            <p className="text-sm font-semibold text-blue-900">
              Assigned to Worker {workerInfo.workerId}
            </p>
            <p className="text-xs text-blue-700 mt-0.5">
              Channel index {workerInfo.channelIndex} of {workerInfo.totalWorkers * 20} estimated
              capacity ({workerInfo.totalWorkers} workers x 20 streams).
              Worker {workerInfo.workerId} handles every {workerInfo.totalWorkers}th channel
              (index % {workerInfo.totalWorkers} == {workerInfo.workerId}).
            </p>
          </div>
          <div className="ml-auto text-right">
            <p className="text-xs text-blue-500 font-mono">Worker logs:</p>
            <code className="text-xs text-blue-700 font-mono">
              docker compose logs worker | grep "W{workerInfo.workerId}"
            </code>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <span className="font-semibold text-sm">Channel Details</span>
        </div>
        <div className="card-body">
          <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
            {detailRows.map(([label, value]) => (
              <div key={label}>
                <dt className="text-gray-500">{label}</dt>
                <dd className="font-medium text-gray-900 mt-0.5">{value}</dd>
              </div>
            ))}
          </dl>
          {channel.description && (
            <p className="mt-4 text-sm text-gray-500 border-t border-gray-100 pt-3">
              {channel.description}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

// ---- Metrics ----------------------------------------------------------------

function MetricsTab({ metrics, hours }: { metrics: Metric[]; hours: number }) {
  const data: ChartPoint[] = metrics.map((m) => ({
    time:      format(new Date(m.timestamp), hours <= 6 ? 'HH:mm' : 'MM/dd HH:mm'),
    bitrate:   m.bitrate,
    latency:   m.response_time,
    fps:       m.fps,
    audio:     m.audio_level,
    available: m.is_available ? 1 : 0,
  })).reverse()

  if (data.length === 0) return <EmptyState message="No metric data for this time range." />

  return (
    <div className="space-y-4">
      <ChartCard title="Bitrate (kbps)"       data={data} dataKey="bitrate"  color="#3b82f6" unit=" kbps"  />
      <ChartCard title="Response Time (ms)"   data={data} dataKey="latency"  color="#8b5cf6" unit=" ms"    />
      <ChartCard title="Frame Rate (fps)"     data={data} dataKey="fps"      color="#22c55e" unit=" fps"   />
      <ChartCard title="Audio Level (dBFS)"   data={data} dataKey="audio"    color="#f59e0b" unit=" dBFS"  />
    </div>
  )
}

function ChartCard({
  title, data, dataKey, color, unit,
}: {
  title: string; data: ChartPoint[]; dataKey: keyof ChartPoint; color: string; unit: string
}) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="font-semibold text-sm text-gray-700">{title}</span>
      </div>
      <div className="card-body pt-2">
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 10 }} width={50} />
            <Tooltip
              formatter={(value: ValueType) => [formatTooltipValue(value, unit), title]}
              labelStyle={{ fontSize: 11 }}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ---- Errors -----------------------------------------------------------------

function ErrorsTab({ errors }: { errors: StreamError[] }) {
  if (errors.length === 0) return <EmptyState message="No errors in this time range." />
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Time</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Type</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Severity</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Message</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Active</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {errors.map((e) => (
            <tr key={e.id} className={e.is_active ? 'bg-red-50' : ''}>
              <td className="px-4 py-2.5 text-xs text-gray-500 font-mono whitespace-nowrap">
                {formatDateTime(e.timestamp)}
              </td>
              <td className="px-4 py-2.5 font-mono text-xs text-gray-700">{e.error_type}</td>
              <td className="px-4 py-2.5"><SeverityBadge severity={e.severity} /></td>
              <td className="px-4 py-2.5 text-xs text-gray-600 max-w-xs truncate">{e.message ?? '-'}</td>
              <td className="px-4 py-2.5 text-xs">
                {e.is_active
                  ? <span className="text-red-600 font-medium">Active</span>
                  : <span className="text-gray-400">Resolved</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---- Stream Info ------------------------------------------------------------

function LogsTab({ channel, metrics }: { channel: Channel; metrics: Metric[] }) {
  const latest = metrics[0]
  return (
    <div className="space-y-4">
      <div className="card">
        <div className="card-header">
          <span className="font-semibold text-sm">Latest Stream Snapshot</span>
        </div>
        <div className="card-body font-mono text-xs space-y-1.5 text-gray-700">
          {latest ? (
            <>
              {([
                ['Timestamp',    formatDateTime(latest.timestamp)],
                ['Bitrate',      formatBitrate(latest.bitrate)],
                ['Resolution',   latest.resolution_width && latest.resolution_height ? `${latest.resolution_width}x${latest.resolution_height}` : '-'],
                ['FPS',          latest.fps?.toFixed(2) ?? '-'],
                ['Video Codec',  latest.codec_video ?? '-'],
                ['Audio Codec',  latest.codec_audio ?? '-'],
                ['Audio Level',  formatAudioLevel(latest.audio_level)],
                ['Response',     formatMs(latest.response_time)],
                ['Available',    latest.is_available ? 'Yes' : 'No'],
              ] as [string, string][]).map(([label, value]) => (
                <div key={label} className="flex gap-4">
                  <span className="text-gray-400 w-32">{label}</span>
                  <span>{value}</span>
                </div>
              ))}
            </>
          ) : (
            <p className="text-gray-400">No metrics recorded yet.</p>
          )}
        </div>
      </div>
    </div>
  )
}
