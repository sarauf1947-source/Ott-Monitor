import { Fragment, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Search, RefreshCw, BellRing, ChevronDown, ChevronRight, Filter, ExternalLink, ShieldAlert } from 'lucide-react'

import { useAlerts, useAcknowledgeAlert, useChannels, useResolveAlert } from '@/hooks/useApi'
import { PageHeader, PageLoader, ErrorDisplay, SeverityBadge } from '@/components/common'
import { cn, formatDateTime, formatRelativeTime } from '@/utils'
import type { AlertStatus, ErrorSeverity } from '@/types'

const STATUS_OPTS: (AlertStatus | 'ALL')[] = ['ALL', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED']
const SEV_OPTS: (ErrorSeverity | 'ALL')[] = ['ALL', 'CRITICAL', 'MAJOR', 'WARNING', 'INFO']
const TIMELINES = [
  { label: '15m', value: 15 },
  { label: '1h', value: 60 },
  { label: '6h', value: 360 },
  { label: '24h', value: 1440 },
] as const

export default function AlertsPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const highlightId = new URLSearchParams(location.search).get('highlight')

  const [status, setStatus] = useState<AlertStatus | 'ALL'>('ALL')
  const [severity, setSeverity] = useState<ErrorSeverity | 'ALL'>('ALL')
  const [channelFilter, setChannelFilter] = useState('')
  const [search, setSearch] = useState('')
  const [timelineMin, setTimelineMin] = useState<number>(60)
  const [workerFilter, setWorkerFilter] = useState('ALL')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const since = useMemo(() => {
    const d = new Date(Date.now() - timelineMin * 60 * 1000)
    return d.toISOString()
  }, [timelineMin])

  const { data: channelList } = useChannels({ page: 1, per_page: 200, is_active: true })
  const channels = channelList?.items ?? []
  const {
    data,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useAlerts({
    status: status !== 'ALL' ? status : undefined,
    severity: severity !== 'ALL' ? severity : undefined,
    channel: channelFilter || undefined,
    search: search || undefined,
    worker_shard: workerFilter !== 'ALL' ? Number(workerFilter) : undefined,
    date_from: since,
    limit: 250,
  })

  const ack = useAcknowledgeAlert()
  const resolve = useResolveAlert()

  useEffect(() => {
    if (highlightId) {
      setExpanded(prev => new Set(prev).add(highlightId))
    }
  }, [highlightId])

  const alerts = data?.items ?? []
  const workerOptions = Array.from(
    new Set(alerts.map(alert => alert.worker_shard).filter((value): value is number => value !== null && value !== undefined))
  ).sort((a, b) => a - b)

  const toggleExpanded = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  if (isLoading) return <PageLoader />
  if (error) return <div className="p-6"><ErrorDisplay message="Failed to load alerts." /></div>

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Alerts Workspace"
        subtitle={`${data?.summary.total ?? 0} alerts across the current filters`}
        actions={
          <button
            onClick={() => refetch()}
            className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors', isFetching && 'opacity-60')}>
            <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      <div className="flex-1 overflow-hidden flex flex-col">
        {data && (
          <div className="flex items-center gap-3 px-6 py-3 bg-white border-b border-gray-200 flex-wrap">
            <ShieldAlert size={14} className="text-gray-400" />
            <SummaryChip label="Open" value={data.summary.open} tone="red" active={status === 'OPEN'} onClick={() => setStatus('OPEN')} />
            <SummaryChip label="Acknowledged" value={data.summary.acknowledged} tone="amber" active={status === 'ACKNOWLEDGED'} onClick={() => setStatus('ACKNOWLEDGED')} />
            <SummaryChip label="Resolved" value={data.summary.resolved} tone="green" active={status === 'RESOLVED'} onClick={() => setStatus('RESOLVED')} />
            <SummaryChip label="Critical" value={data.summary.critical} tone="red" active={severity === 'CRITICAL'} onClick={() => setSeverity('CRITICAL')} />
            <SummaryChip label="Major" value={data.summary.major} tone="amber" active={severity === 'MAJOR'} onClick={() => setSeverity('MAJOR')} />
            <SummaryChip label="Warning" value={data.summary.warning} tone="violet" active={severity === 'WARNING'} onClick={() => setSeverity('WARNING')} />
            <SummaryChip label="Info" value={data.summary.info} tone="blue" active={severity === 'INFO'} onClick={() => setSeverity('INFO')} />
          </div>
        )}

        <div className="px-6 py-3 bg-white border-b border-gray-200 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1">
            {STATUS_OPTS.map(opt => (
              <button
                key={opt}
                onClick={() => setStatus(opt)}
                className={cn(
                  'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                  status === opt ? 'bg-gray-800 text-white' : 'text-gray-500 hover:bg-gray-100'
                )}>
                {opt}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1">
            {SEV_OPTS.map(opt => (
              <button
                key={opt}
                onClick={() => setSeverity(opt)}
                className={cn(
                  'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                  severity === opt ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'
                )}>
                {opt}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5 border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white">
            <Search size={12} className="text-gray-400" />
            <input
              className="text-xs outline-none w-44 placeholder-gray-400"
              placeholder="Search alert text..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <input
            className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 w-44 placeholder-gray-400"
            placeholder="Filter by channel..."
            value={channelFilter}
            onChange={e => setChannelFilter(e.target.value)}
            list="alert-channel-options"
          />
          <datalist id="alert-channel-options">
            {channels.map(channel => <option key={channel.id} value={channel.name} />)}
          </datalist>

          <select
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
            value={workerFilter}
            onChange={e => setWorkerFilter(e.target.value)}>
            <option value="ALL">All workers</option>
            {workerOptions.map(worker => (
              <option key={worker} value={worker}>Worker {String(worker).padStart(2, '0')}</option>
            ))}
          </select>

          <div className="flex items-center gap-1 ml-auto">
            <Filter size={12} className="text-gray-400" />
            {TIMELINES.map(opt => (
              <button
                key={opt.value}
                onClick={() => setTimelineMin(opt.value)}
                className={cn(
                  'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                  timelineMin === opt.value ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:bg-gray-100'
                )}>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          {alerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <BellRing size={32} className="mb-3 opacity-30" />
              <p className="text-sm">No alerts match your filters</p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
                  <th className="w-6 px-3 py-2.5" />
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500">Severity</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500">Channel</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500">Worker</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500">Details</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500">Triggered</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500">Resolved</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500">Status</th>
                  <th className="px-3 py-2.5 text-right font-semibold text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {alerts.map(alert => {
                  const isExpanded = expanded.has(alert.id)
                  return (
                    <Fragment key={alert.id}>
                      <tr
                        className={cn(
                          'hover:bg-gray-50 transition-colors cursor-pointer',
                          highlightId === alert.id && 'bg-blue-50'
                        )}
                        onClick={() => toggleExpanded(alert.id)}>
                        <td className="px-3 py-2 text-center">
                          {isExpanded ? <ChevronDown size={12} className="text-gray-400" /> : <ChevronRight size={12} className="text-gray-400" />}
                        </td>
                        <td className="px-3 py-2"><SeverityBadge severity={alert.severity} /></td>
                        <td className="px-3 py-2">
                          <div className="font-semibold text-gray-800">{alert.channel_name ?? 'Unknown channel'}</div>
                          <div className="text-[11px] text-gray-400">{alert.channel_group ?? alert.channel_status ?? '-'}</div>
                        </td>
                        <td className="px-3 py-2">
                          <div className="font-medium text-gray-700">{alert.worker_label ?? '-'}</div>
                          <div className="text-[11px] text-gray-400">Shard {alert.worker_shard ?? '-'}</div>
                        </td>
                        <td className="px-3 py-2 max-w-[320px]">
                          <div className="font-mono text-[11px] text-gray-500">{alert.alert_type}</div>
                          <div className="truncate text-gray-700" title={alert.message ?? ''}>{alert.message ?? 'No additional details'}</div>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-gray-500">
                          <div>{formatDateTime(alert.triggered_at)}</div>
                          <div className="text-[11px] text-gray-400">{formatRelativeTime(alert.triggered_at)}</div>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-gray-500">
                          {alert.resolved_at ? (
                            <>
                              <div>{formatDateTime(alert.resolved_at)}</div>
                              <div className="text-[11px] text-gray-400">{formatRelativeTime(alert.resolved_at)}</div>
                            </>
                          ) : (
                            <span className="text-gray-300">Still open</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <div className={`text-xs font-semibold ${alert.status === 'OPEN' ? 'text-red-600' : alert.status === 'ACKNOWLEDGED' ? 'text-amber-600' : 'text-green-600'}`}>{alert.status}</div>
                          <div className="text-[11px] text-gray-400">{alert.notification_sent ? 'Notified' : 'Pending notify'}</div>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex justify-end gap-2">
                            <button
                              className="text-xs text-blue-600 hover:underline"
                              onClick={(event) => {
                                event.stopPropagation()
                                navigate(`/channels/${alert.channel_id}`)
                              }}>
                              Channel
                            </button>
                            {alert.status === 'OPEN' && (
                              <button
                                className="text-xs text-amber-600 hover:underline"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  ack.mutate({ id: alert.id, by: 'operator' })
                                }}>
                                Ack
                              </button>
                            )}
                            {alert.status !== 'RESOLVED' && (
                              <button
                                className="text-xs text-green-600 hover:underline"
                                onClick={(event) => {
                                  event.stopPropagation()
                                  resolve.mutate(alert.id)
                                }}>
                                Resolve
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${alert.id}-expanded`} className="bg-slate-50/70">
                          <td colSpan={9} className="px-6 py-4">
                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                              <DetailCard label="Alert">
                                <div className="space-y-1">
                                  <div className="text-sm font-semibold text-gray-800">{alert.alert_type}</div>
                                  <div className="text-sm text-gray-600">{alert.message ?? 'No extra details recorded.'}</div>
                                </div>
                              </DetailCard>
                              <DetailCard label="Channel Context">
                                <div className="space-y-1 text-sm text-gray-600">
                                  <div><span className="font-semibold text-gray-800">Name:</span> {alert.channel_name ?? '-'}</div>
                                  <div><span className="font-semibold text-gray-800">Group:</span> {alert.channel_group ?? '-'}</div>
                                  <div><span className="font-semibold text-gray-800">Status:</span> {alert.channel_status ?? '-'}</div>
                                </div>
                              </DetailCard>
                              <DetailCard label="Lifecycle">
                                <div className="space-y-1 text-sm text-gray-600">
                                  <div><span className="font-semibold text-gray-800">Triggered:</span> {formatDateTime(alert.triggered_at)}</div>
                                  <div><span className="font-semibold text-gray-800">Acknowledged:</span> {alert.acknowledged_at ? `${formatDateTime(alert.acknowledged_at)} by ${alert.acknowledged_by ?? 'operator'}` : 'Not acknowledged'}</div>
                                  <div><span className="font-semibold text-gray-800">Resolved:</span> {alert.resolved_at ? formatDateTime(alert.resolved_at) : 'Not resolved'}</div>
                                </div>
                              </DetailCard>
                            </div>
                            <div className="mt-4 flex gap-3">
                              <button
                                onClick={() => navigate(`/channels/${alert.channel_id}`)}
                                className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-100">
                                Open Channel
                                <ExternalLink size={12} />
                              </button>
                              <button
                                onClick={() => navigate(`/alerts?highlight=${alert.id}`)}
                                className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50">
                                Focus Alert
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

function SummaryChip({ label, value, tone, active, onClick }: {
  label: string
  value: number
  tone: 'red' | 'amber' | 'green' | 'blue' | 'violet'
  active?: boolean
  onClick: () => void
}) {
  const tones: Record<string, string> = {
    red: 'bg-red-50 text-red-700 border-red-100',
    amber: 'bg-amber-50 text-amber-700 border-amber-100',
    green: 'bg-green-50 text-green-700 border-green-100',
    blue: 'bg-blue-50 text-blue-700 border-blue-100',
    violet: 'bg-violet-50 text-violet-700 border-violet-100',
  }
  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition-all',
        tones[tone],
        active && 'ring-2 ring-offset-1 ring-gray-300'
      )}>
      <span>{label}</span>
      <span className="tabular-nums">{value}</span>
    </button>
  )
}

function DetailCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">{label}</div>
      {children}
    </div>
  )
}
