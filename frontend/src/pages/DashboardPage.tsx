import { Activity, TrendingUp, AlertTriangle, CheckCircle, XCircle, Radio } from 'lucide-react'
import { useDashboardSummary, useDashboardChannels } from '@/hooks/useApi'
import { StatCard, PageLoader, ErrorDisplay, PageHeader, StatusBadge, SeverityBadge } from '@/components/common'
import { formatBitrate, formatMs, formatRelativeTime, STATUS_CONFIG, cn } from '@/utils'
import type { ChannelStatusSummary } from '@/types'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function DashboardPage() {
  const { data: summary, isLoading: sumLoading, error: sumError } = useDashboardSummary()
  const { data: channels, isLoading: chLoading } = useDashboardChannels()

  if (sumLoading) return <PageLoader />
  if (sumError) return (
    <div className="p-6">
      <ErrorDisplay message="Failed to load dashboard summary. Is the API running?" />
    </div>
  )

  const sc = summary!.status_counts
  const statusChartData = [
    { name: 'UP',      value: sc['UP'] ?? 0,      fill: '#22c55e' },
    { name: 'DOWN',    value: sc['DOWN'] ?? 0,     fill: '#ef4444' },
    { name: 'ERROR',   value: sc['ERROR'] ?? 0,    fill: '#f59e0b' },
    { name: 'WARNING', value: sc['WARNING'] ?? 0,  fill: '#a855f7' },
    { name: 'UNKNOWN', value: sc['UNKNOWN'] ?? 0,  fill: '#9ca3af' },
  ].filter(d => d.value > 0)

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="NOC Dashboard"
        subtitle={`Live monitoring · Last updated ${formatRelativeTime(summary?.last_updated)}`}
        actions={
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className="pulse-dot-green" />
            Auto-refresh every 10s
          </div>
        }
      />

      <div className="flex-1 overflow-auto p-6 space-y-6">
        {/* KPI Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Channels"
            value={summary!.total_channels}
            icon={<Radio size={20} />}
          />
          <StatCard
            label="Availability"
            value={`${summary!.availability_pct.toFixed(1)}%`}
            sub="last check cycle"
            color={summary!.availability_pct >= 95 ? 'text-green-600' : 'text-red-600'}
            icon={<CheckCircle size={20} />}
          />
          <StatCard
            label="Open Alerts"
            value={summary!.open_alerts}
            sub={`${summary!.critical_alerts} critical`}
            color={summary!.open_alerts > 0 ? 'text-red-600' : 'text-gray-900'}
            icon={<AlertTriangle size={20} />}
          />
          <StatCard
            label="Avg Bitrate"
            value={formatBitrate(summary!.avg_bitrate_kbps)}
            sub={`Avg latency ${formatMs(summary!.avg_response_time_ms)}`}
            icon={<TrendingUp size={20} />}
          />
        </div>

        {/* Status breakdown + Top Errors */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Status chart */}
          <div className="card col-span-1">
            <div className="card-header">
              <span className="font-semibold text-sm text-gray-700">Status Breakdown</span>
            </div>
            <div className="card-body">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={statusChartData} barSize={32}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [v, 'Channels']} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {statusChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {/* Status count pills */}
              <div className="flex flex-wrap gap-2 mt-3">
                {statusChartData.map(d => (
                  <div key={d.name} className="flex items-center gap-1.5 text-xs text-gray-600">
                    <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: d.fill }} />
                    {d.name}: <span className="font-bold">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Top errors */}
          <div className="card col-span-2">
            <div className="card-header">
              <span className="font-semibold text-sm text-gray-700">Top Error Types</span>
            </div>
            <div className="card-body">
              {summary!.top_errors.length === 0 ? (
                <p className="text-center text-gray-400 text-sm py-8">No errors recorded 🎉</p>
              ) : (
                <div className="space-y-2">
                  {summary!.top_errors.map((e, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <SeverityBadge severity={e.severity as never} />
                      <span className="text-sm text-gray-700 font-mono flex-1">{e.error_type}</span>
                      <span className="text-sm font-bold text-gray-900 tabular-nums">{e.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Channel Grid */}
        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-sm text-gray-700">
              Channel Status Grid
              {chLoading && <span className="ml-2 text-xs text-gray-400">Loading…</span>}
            </span>
            <span className="text-xs text-gray-400">{channels?.length ?? 0} channels</span>
          </div>
          <div className="card-body p-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
              {channels?.map(ch => (
                <ChannelCard key={ch.id} channel={ch} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ChannelCard({ channel: ch }: { channel: ChannelStatusSummary }) {
  const navigate = useNavigate()
  const cfg = STATUS_CONFIG[ch.status]

  return (
    <button
      onClick={() => navigate(`/channels/${ch.id}`)}
      className={cn(
        'text-left rounded-lg border p-2.5 transition-all hover:shadow-md hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-blue-500',
        cfg.bg,
        ch.status === 'DOWN' ? 'border-red-200' :
        ch.status === 'ERROR' ? 'border-amber-200' :
        ch.status === 'WARNING' ? 'border-purple-200' :
        ch.status === 'UP' ? 'border-green-200' : 'border-gray-200'
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className={cn('w-2 h-2 rounded-full flex-shrink-0', cfg.dot)} />
        <span className="text-xs font-mono text-gray-500 truncate ml-1">
          {ch.bitrate ? `${Math.round(ch.bitrate / 1000 * 10) / 10}M` : '—'}
        </span>
      </div>
      <div className={cn('text-xs font-semibold truncate', cfg.color)} title={ch.name}>
        {ch.name}
      </div>
      <div className="text-xs text-gray-400 truncate mt-0.5">
        {ch.resolution ?? ch.group ?? '—'}
      </div>
      {ch.last_error_type && (
        <div className="text-xs text-amber-600 truncate mt-0.5 font-mono">
          {ch.last_error_type}
        </div>
      )}
    </button>
  )
}
