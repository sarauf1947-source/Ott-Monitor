// frontend/src/pages/LogsPage.tsx  (v2.2)
// Professional application log viewer with search, filter, retention, email
import { useState, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Trash2, Mail, RefreshCw, ChevronDown, ChevronRight, BarChart2 } from 'lucide-react'
import { apiV2 } from '@/services/apiV2'
import { PageHeader, PageLoader } from '@/components/common'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/utils'

// ---- types ------------------------------------------------------------------
interface LogEntry {
  id:        number
  timestamp: string
  level:     string
  logger:    string
  message:   string
  exception: string | null
  source:    string | null
}

interface LogStats {
  debug: number; info: number; warning: number; error: number; critical: number; total: number
}

// ---- constants --------------------------------------------------------------
const LEVELS = ['ALL', 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'] as const
const LEVEL_STYLE: Record<string, string> = {
  CRITICAL: 'bg-red-100 text-red-800 border-red-200',
  ERROR:    'bg-red-50  text-red-700  border-red-100',
  WARNING:  'bg-amber-50 text-amber-700 border-amber-100',
  INFO:     'bg-blue-50 text-blue-700  border-blue-100',
  DEBUG:    'bg-gray-50  text-gray-600  border-gray-100',
}
const LEVEL_DOT: Record<string, string> = {
  CRITICAL: 'bg-red-600',
  ERROR:    'bg-red-400',
  WARNING:  'bg-amber-400',
  INFO:     'bg-blue-400',
  DEBUG:    'bg-gray-400',
}

// ---- API helpers ------------------------------------------------------------
const fetchLogs = (params: Record<string, string | number>) =>
  apiV2.get('/logs', { params }).then(r => r.data)

const fetchStats = () =>
  apiV2.get('/logs/stats?hours=24').then(r => r.data)

const purgeOlderThan = (days: number) =>
  apiV2.delete(`/logs/purge?days=${days}`)

const emailLog = (id: number, to_email: string) =>
  apiV2.post(`/logs/${id}/email`, { to_email })

// ---- component --------------------------------------------------------------
export default function LogsPage() {
  const { isAdmin } = useAuth()
  const qc          = useQueryClient()

  // Filters
  const [level,      setLevel]      = useState('ALL')
  const [search,     setSearch]     = useState('')
  const [loggerFilter, setLogger]   = useState('')
  const [since,      setSince]      = useState('')
  const [until,      setUntil]      = useState('')
  const [limit,      setLimit]      = useState(200)

  // UI state
  const [expanded,     setExpanded]     = useState<Set<number>>(new Set<number>())
  const [emailTarget,  setEmailTarget]  = useState<LogEntry | null>(null)
  const [emailAddr,    setEmailAddr]    = useState('')
  const [retentionDays,setRetentionDays]= useState(30)
  const [purgeMsg,     setPurgeMsg]     = useState('')
  const [emailMsg,     setEmailMsg]     = useState('')

  // Build query params
  const params: Record<string, string | number> = { limit }
  if (level !== 'ALL')  params.level  = level
  if (search.trim())    params.search = search.trim()
  if (loggerFilter.trim()) params.logger = loggerFilter.trim()
  if (since) params.since = since
  if (until) params.until = until

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['logs', params],
    queryFn:  () => fetchLogs(params),
    refetchInterval: 30_000,
  })

  const { data: stats } = useQuery<LogStats>({
    queryKey: ['logs', 'stats'],
    queryFn:  fetchStats,
    refetchInterval: 60_000,
  })

  const purgeMut = useMutation({
    mutationFn: () => purgeOlderThan(retentionDays),
    onSuccess: (res) => {
      const deleted = (res as { data: { deleted: number } }).data?.deleted ?? 0
      setPurgeMsg(`Deleted ${deleted} log entries older than ${retentionDays} days`)
      qc.invalidateQueries({ queryKey: ['logs'] })
      setTimeout(() => setPurgeMsg(''), 4000)
    },
    onError: () => setPurgeMsg('Purge failed'),
  })

  const emailMut = useMutation({
    mutationFn: () => emailLog(emailTarget!.id, emailAddr),
    onSuccess: () => { setEmailMsg('Email sent'); setEmailTarget(null); setEmailAddr('') },
    onError: () => setEmailMsg('Failed to send email. Check SMTP settings.'),
  })

  const toggleExpanded = (id: number) => {
    setExpanded(prev => {
      const next = new Set<number>(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const logs: LogEntry[] = data?.items ?? []
  const total: number    = data?.total ?? 0

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Application Logs"
        subtitle={`${total} entries matching filters`}
        actions={
          <button onClick={() => refetch()}
            className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors', isFetching && 'opacity-60')}>
            <RefreshCw size={12} className={isFetching ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      <div className="flex-1 overflow-hidden flex flex-col">

        {/* Stats bar */}
        {stats && (
          <div className="flex items-center gap-3 px-6 py-3 bg-white border-b border-gray-200 flex-wrap">
            <BarChart2 size={14} className="text-gray-400" />
            <span className="text-xs text-gray-500 font-medium">Last 24h:</span>
            {([
              ['CRITICAL', stats.critical, 'text-red-600'],
              ['ERROR',    stats.error,    'text-red-500'],
              ['WARNING',  stats.warning,  'text-amber-600'],
              ['INFO',     stats.info,     'text-blue-600'],
              ['DEBUG',    stats.debug,    'text-gray-500'],
            ] as const).map(([lbl, cnt, cls]) => (
              <button key={lbl} onClick={() => setLevel(lbl)}
                className={cn('text-xs font-semibold tabular-nums hover:underline', cls)}>
                {lbl}: {cnt}
              </button>
            ))}
            <span className="text-xs text-gray-400 ml-2">Total: {stats.total}</span>
          </div>
        )}

        {/* Filters */}
        <div className="px-6 py-3 bg-white border-b border-gray-200 flex flex-wrap items-center gap-3">
          {/* Level selector */}
          <div className="flex items-center gap-1">
            {LEVELS.map(l => (
              <button key={l} onClick={() => setLevel(l)}
                className={cn(
                  'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                  level === l
                    ? (l === 'ALL' ? 'bg-gray-700 text-white' : LEVEL_STYLE[l] + ' border font-semibold')
                    : 'text-gray-500 hover:bg-gray-100'
                )}>
                {l}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="flex items-center gap-1.5 border border-gray-200 rounded-lg px-2.5 py-1.5 bg-white">
            <Search size={12} className="text-gray-400" />
            <input
              className="text-xs outline-none w-44 placeholder-gray-400"
              placeholder="Search message..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          {/* Logger filter */}
          <input
            className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 w-36 placeholder-gray-400"
            placeholder="Logger name..."
            value={loggerFilter}
            onChange={e => setLogger(e.target.value)}
          />

          {/* Date range */}
          <input type="datetime-local" className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
            value={since} onChange={e => setSince(e.target.value)} title="From date" />
          <span className="text-gray-400 text-xs">to</span>
          <input type="datetime-local" className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
            value={until} onChange={e => setUntil(e.target.value)} title="To date" />

          {/* Limit */}
          <select className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
            value={limit} onChange={e => setLimit(+e.target.value)}>
            {[100, 200, 500, 1000, 2000].map(n => (
              <option key={n} value={n}>Last {n}</option>
            ))}
          </select>

          {/* Retention / purge (admin only) */}
          {isAdmin && (
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs text-gray-500">Retention:</span>
              <select className="text-xs border border-gray-200 rounded-lg px-2 py-1.5"
                value={retentionDays} onChange={e => setRetentionDays(+e.target.value)}>
                {[7, 14, 30, 60, 90].map(d => (
                  <option key={d} value={d}>{d} days</option>
                ))}
              </select>
              <button
                onClick={() => {
                  if (confirm(`Delete all logs older than ${retentionDays} days?`))
                    purgeMut.mutate()
                }}
                disabled={purgeMut.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-50 text-red-600 hover:bg-red-100 border border-red-100">
                <Trash2 size={12} />
                Purge Old Logs
              </button>
            </div>
          )}
        </div>

        {purgeMsg && (
          <div className="px-6 py-2 bg-green-50 text-green-700 text-xs border-b border-green-100">{purgeMsg}</div>
        )}

        {/* Table */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="p-6"><PageLoader /></div>
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <BarChart2 size={32} className="mb-3 opacity-30" />
              <p className="text-sm">No log entries match your filters</p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
                  <th className="w-6 px-3 py-2.5" />
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500 whitespace-nowrap">Timestamp</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500 w-20">Level</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500 w-48">Logger</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-gray-500">Message</th>
                  <th className="px-3 py-2.5 text-right font-semibold text-gray-500 w-16">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {logs.map(log => (
                  <>
                    <tr key={log.id}
                      className={cn('hover:bg-gray-50 transition-colors', log.exception && 'cursor-pointer')}
                      onClick={() => log.exception && toggleExpanded(log.id)}>
                      <td className="px-3 py-2 text-center">
                        {log.exception ? (
                          expanded.has(log.id)
                            ? <ChevronDown size={12} className="text-gray-400" />
                            : <ChevronRight size={12} className="text-gray-400" />
                        ) : null}
                      </td>
                      <td className="px-3 py-2 font-mono text-gray-500 whitespace-nowrap">
                        {new Date(log.timestamp).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        <span className={cn(
                          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold',
                          LEVEL_STYLE[log.level] ?? 'bg-gray-50 text-gray-600 border-gray-100'
                        )}>
                          <span className={cn('w-1.5 h-1.5 rounded-full', LEVEL_DOT[log.level] ?? 'bg-gray-400')} />
                          {log.level}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono text-gray-600 max-w-48 truncate" title={log.logger}>
                        {log.logger}
                      </td>
                      <td className="px-3 py-2 text-gray-800 max-w-0">
                        <p className="truncate" title={log.message}>{log.message}</p>
                        {log.source && (
                          <p className="text-gray-400 text-xs mt-0.5 truncate">{log.source}</p>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={e => { e.stopPropagation(); setEmailTarget(log); setEmailAddr(''); setEmailMsg('') }}
                          className="p-1 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600 transition-colors"
                          title="Email this log entry">
                          <Mail size={12} />
                        </button>
                      </td>
                    </tr>
                    {log.exception && expanded.has(log.id) && (
                      <tr key={`exp-${log.id}`} className="bg-red-50">
                        <td colSpan={6} className="px-6 py-3">
                          <p className="text-xs font-semibold text-red-700 mb-1">Exception Traceback</p>
                          <pre className="text-xs font-mono text-red-800 whitespace-pre-wrap break-all bg-white border border-red-100 rounded p-3 max-h-64 overflow-y-auto">
                            {log.exception}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Email modal */}
      {emailTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-900 text-sm">Email Log Entry #{emailTarget.id}</h2>
              <button onClick={() => setEmailTarget(null)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">x</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="bg-gray-50 rounded-lg p-3 text-xs font-mono text-gray-700 max-h-24 overflow-auto">
                <span className={cn('inline-block px-1.5 py-0.5 rounded text-xs font-bold mr-2',
                  LEVEL_STYLE[emailTarget.level])}>
                  {emailTarget.level}
                </span>
                {emailTarget.message}
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1.5">Recipient email</label>
                <input
                  className="input"
                  type="email"
                  placeholder="recipient@company.com"
                  value={emailAddr}
                  onChange={e => setEmailAddr(e.target.value)}
                  autoFocus
                />
              </div>
              {emailMsg && (
                <p className={cn('text-xs rounded px-3 py-2',
                  emailMsg.startsWith('Email') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700')}>
                  {emailMsg}
                </p>
              )}
            </div>
            <div className="flex justify-end gap-3 px-6 pb-5">
              <button className="btn-secondary text-sm" onClick={() => setEmailTarget(null)}>Cancel</button>
              <button
                className="btn-primary text-sm"
                onClick={() => emailMut.mutate()}
                disabled={emailMut.isPending || !emailAddr}>
                {emailMut.isPending ? 'Sending...' : 'Send Email'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
