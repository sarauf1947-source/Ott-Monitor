// frontend/src/pages/DashboardPage.tsx  (v2.2)
// Fixes from v2.1:
//   - Set<string> types explicitly typed to fix TypeScript build error
//   - Removed top-right notification button (notifications are in sidebar)
//   - Pinned channels multi-select preserved
//   - Clickable status tiles preserved
import { useState } from 'react'
import { Activity, TrendingUp, AlertTriangle, CheckCircle, Radio, Pin, BellRing, ArrowRight } from 'lucide-react'
import { useDashboardSummary, useDashboardChannels } from '@/hooks/useApi'
import { StatCard, PageLoader, ErrorDisplay, PageHeader, StatusBadge, SeverityBadge } from '@/components/common'
import { formatBitrate, formatMs, formatRelativeTime, STATUS_CONFIG, cn } from '@/utils'
import type { ChannelStatusSummary } from '@/types'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { apiV2, getPinned, setPinned } from '@/services/apiV2'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

export default function DashboardPage() {
  const navigate = useNavigate()
  const qc       = useQueryClient()

  const { data: summary, isLoading: sumLoading, error: sumError } = useDashboardSummary()
  const { data: channels, isLoading: chLoading } = useDashboardChannels()

  const { data: pinnedData } = useQuery({
    queryKey: ['pinned'],
    queryFn:  getPinned,
    retry: 1,
  })

  // Explicitly type Set<string> to avoid TypeScript Set<unknown> inference
  const [selectMode,  setSelectMode]  = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set<string>())

  const pinMutation = useMutation({
    mutationFn: (ids: string[]) => setPinned(ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pinned'] })
      setSelectMode(false)
      setSelectedIds(new Set<string>())
    },
  })

  const pinnedIds  = new Set<string>((pinnedData?.pinned ?? []).map((p: { id: string }) => p.id))
  const pinnedList = (channels ?? []).filter(ch => pinnedIds.has(ch.id))

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set<string>(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const enterSelectMode = () => {
    setSelectedIds(new Set<string>(pinnedIds))
    setSelectMode(true)
  }

  if (sumLoading) return <PageLoader />
  if (sumError) return (
    <div className="p-6">
      <ErrorDisplay message="Failed to load dashboard summary. Is the API running?" />
    </div>
  )

  const sc = summary!.status_counts
  const statusChartData = [
    { name: 'UP',      value: sc['UP']      ?? 0, fill: '#22c55e' },
    { name: 'DOWN',    value: sc['DOWN']    ?? 0, fill: '#ef4444' },
    { name: 'ERROR',   value: sc['ERROR']   ?? 0, fill: '#f59e0b' },
    { name: 'WARNING', value: sc['WARNING'] ?? 0, fill: '#a855f7' },
    { name: 'UNKNOWN', value: sc['UNKNOWN'] ?? 0, fill: '#9ca3af' },
  ].filter(d => d.value > 0)

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="NOC Dashboard"
        subtitle={`Live monitoring - Last updated ${formatRelativeTime(summary?.last_updated)}`}
        actions={
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className="pulse-dot-green" />
            Auto-refresh every 10s
          </div>
        }
      />

      <div className="flex-1 overflow-auto p-6 space-y-6">

        {/* KPI Tiles - clickable */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <button onClick={() => navigate('/channels')} className="text-left hover:ring-2 hover:ring-blue-400 rounded-xl transition-all">
            <StatCard label="Total Channels" value={summary!.total_channels} icon={<Radio size={20} />} />
          </button>
          <button onClick={() => navigate('/channels?status=UP')} className="text-left hover:ring-2 hover:ring-green-400 rounded-xl transition-all">
            <StatCard
              label="Availability"
              value={`${summary!.availability_pct.toFixed(1)}%`}
              sub="click to view UP channels"
              color={summary!.availability_pct >= 95 ? 'text-green-600' : 'text-red-600'}
              icon={<CheckCircle size={20} />}
            />
          </button>
          <button onClick={() => navigate('/alerts')} className="text-left hover:ring-2 hover:ring-red-400 rounded-xl transition-all">
            <StatCard
              label="Open Alerts"
              value={summary!.open_alerts}
              sub={`${summary!.critical_alerts} critical · ${summary!.warning_alerts} warning`}
              color={summary!.open_alerts > 0 ? 'text-red-600' : 'text-gray-900'}
              icon={<AlertTriangle size={20} />}
            />
          </button>
          <button onClick={() => navigate('/reports')} className="text-left hover:ring-2 hover:ring-blue-400 rounded-xl transition-all">
            <StatCard
              label="Avg Bitrate"
              value={formatBitrate(summary!.avg_bitrate_kbps)}
              sub={`Avg latency ${formatMs(summary!.avg_response_time_ms)}`}
              icon={<TrendingUp size={20} />}
            />
          </button>
        </div>

        {/* Status count tiles */}
        <div className="grid grid-cols-5 gap-3">
          {(['UP','DOWN','ERROR','WARNING','UNKNOWN'] as const).map(s => {
            const count = sc[s] ?? 0
            const colors: Record<string, string> = {
              UP:      'border-green-200 bg-green-50 text-green-700',
              DOWN:    'border-red-200 bg-red-50 text-red-700',
              ERROR:   'border-amber-200 bg-amber-50 text-amber-700',
              WARNING: 'border-purple-200 bg-purple-50 text-purple-700',
              UNKNOWN: 'border-gray-200 bg-gray-50 text-gray-600',
            }
            return (
              <button key={s}
                onClick={() => navigate(`/channels?status=${s}`)}
                className={cn('rounded-xl border p-3 text-center transition-all hover:shadow-md hover:scale-105', colors[s])}>
                <div className="text-2xl font-bold tabular-nums">{count}</div>
                <div className="text-xs font-semibold mt-0.5">{s}</div>
              </button>
            )
          })}
        </div>

        {/* Pinned Channels */}
        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-sm text-gray-700">
              Pinned Channels
              {pinnedList.length > 0 && (
                <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{pinnedList.length}</span>
              )}
            </span>
            <div className="flex items-center gap-2">
              {selectMode ? (
                <>
                  <span className="text-xs text-gray-500">{selectedIds.size} selected</span>
                  <button className="btn-primary text-xs py-1 px-3" onClick={() => pinMutation.mutate(Array.from(selectedIds))} disabled={pinMutation.isPending}>
                    {pinMutation.isPending ? 'Saving...' : 'Save Pins'}
                  </button>
                  <button className="btn-secondary text-xs py-1 px-3" onClick={() => setSelectMode(false)}>Cancel</button>
                </>
              ) : (
                <button onClick={enterSelectMode} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 transition-colors">
                  <Pin size={12} />Edit Pins
                </button>
              )}
            </div>
          </div>
          <div className="card-body p-3">
            {selectMode ? (
              <div>
                <p className="text-xs text-gray-500 mb-3 px-1">Click channels to select/deselect. Pinned channels appear at the top of the dashboard.</p>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2 max-h-64 overflow-y-auto">
                  {(channels ?? []).map(ch => (
                    <button key={ch.id} onClick={() => toggleSelect(ch.id)}
                      className={cn(
                        'relative text-left rounded-lg border p-2.5 transition-all text-xs',
                        selectedIds.has(ch.id) ? 'border-blue-400 bg-blue-50 ring-2 ring-blue-400' : 'border-gray-200 hover:border-blue-300'
                      )}>
                      {selectedIds.has(ch.id) && (
                        <span className="absolute top-1 right-1 w-4 h-4 bg-blue-500 rounded-full flex items-center justify-center">
                          <span className="text-white text-xs leading-none">v</span>
                        </span>
                      )}
                      <StatusBadge status={ch.status} />
                      <div className="font-medium truncate mt-1" title={ch.name}>{ch.name}</div>
                    </button>
                  ))}
                </div>
              </div>
            ) : pinnedList.length === 0 ? (
              <div className="text-center py-6 text-gray-400 text-sm">
                <Pin size={20} className="mx-auto mb-2 opacity-40" />
                No channels pinned. Click "Edit Pins" to pin channels here.
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
                {pinnedList.map(ch => <ChannelCard key={ch.id} channel={ch} pinned />)}
              </div>
            )}
          </div>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="card col-span-1">
            <div className="card-header"><span className="font-semibold text-sm text-gray-700">Status Breakdown</span></div>
            <div className="card-body">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={statusChartData} barSize={32}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [v, 'Channels']} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {statusChartData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-2 mt-3">
                {statusChartData.map(d => (
                  <button key={d.name} onClick={() => navigate(`/channels?status=${d.name}`)}
                    className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-blue-600 transition-colors">
                    <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: d.fill }} />
                    {d.name}: <span className="font-bold">{d.value}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="card col-span-2">
            <div className="card-header">
              <span className="font-semibold text-sm text-gray-700">Top Error Types</span>
              <button onClick={() => navigate('/alerts')} className="text-xs text-blue-600 hover:underline">View all</button>
            </div>
            <div className="card-body">
              {summary!.top_errors.length === 0 ? (
                <p className="text-center text-gray-400 text-sm py-8">No errors recorded</p>
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

        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-sm text-gray-700">Recent Alerts</span>
            <button onClick={() => navigate('/alerts')} className="text-xs text-blue-600 hover:underline">Open alerts workspace</button>
          </div>
          <div className="card-body">
            {summary!.recent_alerts.length === 0 ? (
              <p className="text-center text-gray-400 text-sm py-8">No recent alerts to show</p>
            ) : (
              <div className="space-y-2">
                {summary!.recent_alerts.map(alert => (
                  <button
                    key={alert.id}
                    onClick={() => navigate(`/alerts?highlight=${alert.id}`)}
                    className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-left transition-all hover:border-blue-300 hover:bg-blue-50/40">
                    <div className="flex items-start gap-3">
                      <BellRing size={16} className="mt-0.5 text-blue-500" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <SeverityBadge severity={alert.severity as never} />
                          <span className="text-sm font-semibold text-gray-800">{alert.channel_name ?? 'Unknown channel'}</span>
                          <span className="text-xs text-gray-400">{alert.worker_label ?? '-'}</span>
                        </div>
                        <div className="mt-1 text-xs font-mono text-gray-500">{alert.alert_type}</div>
                        <div className="mt-1 text-sm text-gray-700 line-clamp-2">{alert.message ?? 'No additional details provided.'}</div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className={`text-xs font-semibold ${alert.status==='OPEN'?'text-red-600':alert.status==='ACKNOWLEDGED'?'text-amber-600':'text-green-600'}`}>{alert.status}</span>
                        <span className="text-xs text-gray-400 whitespace-nowrap">{formatRelativeTime(alert.triggered_at)}</span>
                        <ArrowRight size={14} className="text-gray-300" />
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* All Channels Grid */}
        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-sm text-gray-700">
              All Channels
              {chLoading && <span className="ml-2 text-xs text-gray-400">Loading...</span>}
            </span>
            <span className="text-xs text-gray-400">{channels?.length ?? 0} channels</span>
          </div>
          <div className="card-body p-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
              {channels?.map(ch => <ChannelCard key={ch.id} channel={ch} />)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ChannelCard({ channel: ch, pinned = false }: { channel: ChannelStatusSummary; pinned?: boolean }) {
  const navigate = useNavigate()
  const cfg      = STATUS_CONFIG[ch.status]
  return (
    <button
      onClick={() => navigate(`/channels/${ch.id}`)}
      className={cn(
        'relative text-left rounded-lg border p-2.5 transition-all hover:shadow-md hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-blue-500',
        cfg.bg,
        ch.status === 'DOWN'    ? 'border-red-200'    :
        ch.status === 'ERROR'   ? 'border-amber-200'  :
        ch.status === 'WARNING' ? 'border-purple-200' :
        ch.status === 'UP'      ? 'border-green-200'  : 'border-gray-200'
      )}>
      {pinned && <Pin size={9} className="absolute top-1.5 right-1.5 text-blue-400 opacity-70" />}
      <div className="flex items-center justify-between mb-1">
        <span className={cn('w-2 h-2 rounded-full flex-shrink-0', cfg.dot)} />
        <span className="text-xs font-mono text-gray-500 truncate ml-1">
          {ch.bitrate ? `${Math.round(ch.bitrate / 1000 * 10) / 10}M` : '-'}
        </span>
      </div>
      <div className={cn('text-xs font-semibold truncate', cfg.color)} title={ch.name}>{ch.name}</div>
      <div className="text-xs text-gray-400 truncate mt-0.5">{ch.resolution ?? ch.group ?? '-'}</div>
      {ch.last_error_type && (
        <div className="text-xs text-amber-600 truncate mt-0.5 font-mono">{ch.last_error_type}</div>
      )}
    </button>
  )
}
