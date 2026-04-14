import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Cpu, HardDrive, RefreshCw, Search, Server, Wifi } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { PageHeader, PageLoader, ErrorDisplay } from '@/components/common'
import { getSystemMetrics, getSystemMetricsHistory } from '@/services/apiV2'
import type { SystemMetricsHistoryPoint, SystemMetricsSnapshot } from '@/types'
import { cn } from '@/utils'

const TIMELINES = [
  { label: '15m', value: 15 },
  { label: '1h', value: 60 },
  { label: '6h', value: 360 },
  { label: '24h', value: 1440 },
] as const

export default function InfrastructurePage() {
  const [timelineMin, setTimelineMin] = useState<number>(60)
  const [search, setSearch] = useState('')
  const [onlyErrors, setOnlyErrors] = useState(false)

  const { data, isLoading, error, isFetching, refetch } = useQuery<SystemMetricsSnapshot>({
    queryKey: ['system', 'metrics'],
    queryFn: getSystemMetrics,
    refetchInterval: 10_000,
  })

  const { data: historyData } = useQuery<{ minutes: number; points: SystemMetricsHistoryPoint[] }>({
    queryKey: ['system', 'metrics-history', timelineMin],
    queryFn: () => getSystemMetricsHistory(timelineMin),
    refetchInterval: 30_000,
  })

  if (isLoading) return <PageLoader />
  if (error || !data) return <div className="p-6"><ErrorDisplay message="Could not load system metrics. Is the API healthy?" /></div>

  const chartPoints = (historyData?.points ?? []).map(point => ({
    ...point,
    time: new Date(point.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    bandwidth_total_mbps: Number((point.bandwidth_sent_mbps + point.bandwidth_recv_mbps).toFixed(3)),
  }))

  const workers = data.workers.details.filter(worker => {
    const haystack = `${worker.worker_id} ${worker.shard_id}`.toLowerCase()
    const matchesSearch = !search.trim() || haystack.includes(search.trim().toLowerCase())
    const matchesErrors = !onlyErrors || worker.streams_error > 0
    return matchesSearch && matchesErrors
  })

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Infrastructure"
        subtitle={`Updated ${new Date(data.timestamp).toLocaleTimeString()}`}
        actions={
          <button
            onClick={() => refetch()}
            className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors', isFetching && 'opacity-60')}>
            <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      <div className="flex-1 overflow-auto p-6 space-y-6">
        <div className="grid grid-cols-2 xl:grid-cols-6 gap-4">
          <StatCard icon={<Cpu size={16} />} label="CPU" value={`${data.server.cpu_percent}%`} sub={`${data.server.cpu_count} cores`} />
          <StatCard icon={<Activity size={16} />} label="Memory" value={`${data.server.memory.percent}%`} sub={`${data.server.memory.used_gb}/${data.server.memory.total_gb} GB`} />
          <StatCard icon={<HardDrive size={16} />} label="Disk" value={`${data.server.disk.percent}%`} sub={`${data.server.disk.used_gb}/${data.server.disk.total_gb} GB`} />
          <StatCard icon={<Wifi size={16} />} label="Bandwidth" value={`${data.server.network.bandwidth_recv_mbps + data.server.network.bandwidth_sent_mbps} MB/s`} sub={`In ${data.server.network.bandwidth_recv_mbps} · Out ${data.server.network.bandwidth_sent_mbps}`} />
          <StatCard icon={<Server size={16} />} label="Workers" value={String(data.workers.active_count)} sub={`${data.workers.assigned_total} assigned`} />
          <StatCard icon={<Activity size={16} />} label="Queue Depth" value={String(data.workers.queue_depth)} sub={`${data.workers.error_total} current errors`} />
        </div>

        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-sm text-gray-700">Trends</span>
            <div className="flex items-center gap-2">
              {TIMELINES.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setTimelineMin(opt.value)}
                  className={cn('px-2.5 py-1 rounded-md text-xs font-medium transition-colors', timelineMin === opt.value ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:bg-gray-100')}>
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <div className="card-body grid grid-cols-1 xl:grid-cols-2 gap-4">
            <MetricChart title="CPU Usage" color="#2563eb" dataKey="cpu_percent" points={chartPoints} />
            <MetricChart title="Memory Usage" color="#16a34a" dataKey="memory_percent" points={chartPoints} />
            <MetricChart title="Disk Usage" color="#d97706" dataKey="disk_percent" points={chartPoints} />
            <MetricChart title="Bandwidth" color="#7c3aed" dataKey="bandwidth_total_mbps" points={chartPoints} suffix=" MB/s" decimals={2} />
            <WorkerTrendChart title="Worker Throughput" points={chartPoints} />
            <WorkerTrendChart title="Worker Errors vs Queue" points={chartPoints} showQueue />
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="font-semibold text-sm text-gray-700">Workers</span>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white">
                <Search size={12} className="text-gray-400" />
                <input
                  className="text-xs outline-none w-40 placeholder-gray-400"
                  placeholder="Search instance or shard..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </div>
              <button
                onClick={() => setOnlyErrors(v => !v)}
                className={cn('px-2.5 py-1 rounded-md text-xs font-medium transition-colors', onlyErrors ? 'bg-red-600 text-white' : 'text-gray-500 hover:bg-gray-100')}>
                Errors only
              </button>
            </div>
          </div>
          <div className="card-body p-0">
            {workers.length === 0 ? (
              <p className="text-sm text-gray-400 p-6">No worker stats match the current filters.</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    {['Worker Name', 'Instance ID', 'Shard', 'Assigned', 'Probe Slots', 'Queued Alerts', 'OK', 'Errors', 'Last Cycle', 'Updated'].map(h => (
                      <th key={h} className="px-3 py-2 text-left font-semibold text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {workers.map(worker => (
                    <tr key={worker.worker_id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-semibold text-gray-800">{`Worker ${String(worker.shard_id).padStart(2, '0')}`}</td>
                      <td className="px-3 py-2 font-mono text-gray-500">{worker.worker_id}</td>
                      <td className="px-3 py-2">{worker.shard_id}</td>
                      <td className="px-3 py-2">{worker.streams_assigned}</td>
                      <td className="px-3 py-2">{worker.probe_concurrency}</td>
                      <td className={`px-3 py-2 font-semibold ${worker.notification_queue_depth > 0 ? 'text-amber-600' : 'text-gray-400'}`}>{worker.notification_queue_depth}</td>
                      <td className="px-3 py-2 text-green-600 font-semibold">{worker.streams_ok}</td>
                      <td className={`px-3 py-2 font-semibold ${worker.streams_error > 0 ? 'text-red-600' : 'text-gray-400'}`}>{worker.streams_error}</td>
                      <td className="px-3 py-2">{worker.last_cycle_sec.toFixed(1)}s</td>
                      <td className="px-3 py-2 text-gray-400">{new Date(worker.last_updated).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub: string }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4">
      <div className="flex items-center gap-2 text-gray-500 text-xs font-semibold uppercase tracking-wide">
        {icon}
        {label}
      </div>
      <div className="mt-3 text-2xl font-bold text-gray-900">{value}</div>
      <div className="mt-1 text-xs text-gray-400">{sub}</div>
    </div>
  )
}

function MetricChart({
  title,
  color,
  dataKey,
  points,
  suffix = '%',
  decimals = 1,
}: {
  title: string
  color: string
  dataKey: string
  points: Array<Record<string, string | number>>
  suffix?: string
  decimals?: number
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="text-sm font-semibold text-gray-700 mb-3">{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={points}>
          <defs>
            <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="time" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(value: number) => [`${Number(value).toFixed(decimals)}${suffix}`, title]} />
          <Area type="monotone" dataKey={dataKey} stroke={color} fill={`url(#grad-${dataKey})`} strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function WorkerTrendChart({
  title,
  points,
  showQueue = false,
}: {
  title: string
  points: Array<Record<string, string | number>>
  showQueue?: boolean
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="text-sm font-semibold text-gray-700 mb-3">{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={points}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="time" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          {!showQueue ? (
            <>
              <Line type="monotone" dataKey="workers_assigned" stroke="#2563eb" strokeWidth={2} dot={false} name="Assigned" />
              <Line type="monotone" dataKey="workers_ok" stroke="#16a34a" strokeWidth={2} dot={false} name="OK" />
              <Line type="monotone" dataKey="workers_error" stroke="#dc2626" strokeWidth={2} dot={false} name="Errors" />
            </>
          ) : (
            <>
              <Line type="monotone" dataKey="workers_error" stroke="#dc2626" strokeWidth={2} dot={false} name="Errors" />
              <Line type="monotone" dataKey="queue_depth" stroke="#d97706" strokeWidth={2} dot={false} name="Queue Depth" />
              <Line type="monotone" dataKey="workers_active" stroke="#6366f1" strokeWidth={2} dot={false} name="Active Workers" />
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
