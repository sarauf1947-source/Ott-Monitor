// frontend/src/pages/ReportsPage.tsx
// REPLACES existing ReportsPage.tsx
// New features: predefined report templates, XLSX download, stream URL diagnostics
import { useState } from 'react'
import { FileDown, PlayCircle, BarChart2, AlertTriangle, Tv2, Search } from 'lucide-react'
import axios from 'axios'
import { generateReport, downloadCsvReport } from '@/services/api'
import { apiV2, downloadReport } from '@/services/apiV2'
import { PageHeader, Spinner } from '@/components/common'
import { formatBitrate } from '@/utils'
import { useQuery } from '@tanstack/react-query'
import { fetchChannels } from '@/services/api'

type Tab = 'custom' | 'predefined' | 'diagnostic'

export default function ReportsPage() {
  const [tab, setTab] = useState<Tab>('predefined')

  return (
    <div className="flex flex-col h-full">
      <PageHeader title="Reports" subtitle="Generate availability, quality and error reports" />

      {/* Tabs */}
      <div className="flex border-b border-gray-200 px-6 gap-1 bg-white">
        {([
          { key: 'predefined' as Tab, label: 'Predefined Reports',  icon: BarChart2 },
          { key: 'custom'     as Tab, label: 'Custom Report',        icon: PlayCircle },
          { key: 'diagnostic' as Tab, label: 'Stream Diagnostics',   icon: Search },
        ] as const).map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto p-6">
        {tab === 'predefined'  && <PredefinedTab />}
        {tab === 'custom'      && <CustomTab />}
        {tab === 'diagnostic'  && <DiagnosticTab />}
      </div>
    </div>
  )
}

// ---- Predefined Reports -------------------------------------------------------
function PredefinedTab() {
  const [days,      setDays]      = useState(7)
  const [loading,   setLoading]   = useState<string | null>(null)
  const [data,      setData]      = useState<Record<string, unknown> | null>(null)
  const [activeRpt, setActiveRpt] = useState<string | null>(null)
  const [error,     setError]     = useState('')

  const templates = [
    { key: 'uptime',   label: 'Uptime / Downtime',  icon: Tv2,          color: 'text-green-600 bg-green-50 border-green-200',   desc: 'Availability % per channel' },
    { key: 'errors',   label: 'Error Breakdown',     icon: AlertTriangle, color: 'text-red-600 bg-red-50 border-red-200',         desc: 'Error counts by type and severity' },
    { key: 'bitrate',  label: 'Bitrate Trends',      icon: BarChart2,    color: 'text-blue-600 bg-blue-50 border-blue-200',      desc: 'Avg bitrate vs expected per channel' },
  ]

  const run = async (key: string) => {
    setLoading(key); setError(''); setData(null); setActiveRpt(key)
    try {
      const res = await apiV2.get(`/reports/predefined/${key}?days=${days}`)
      setData(res.data)
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Report failed')
    } finally { setLoading(null) }
  }

  const downloadXlsx = async (channelId?: string) => {
    if (channelId) {
      const res = await downloadReport(channelId, 'xlsx', days)
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a'); a.href = url
      a.download = `report_${channelId}.xlsx`; a.click()
      URL.revokeObjectURL(url)
    }
  }

  return (
    <div className="space-y-5">
      {/* Days selector */}
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-gray-700">Time period:</label>
        {[1, 7, 14, 30].map(d => (
          <button key={d} onClick={() => setDays(d)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              days === d ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-200 hover:border-blue-400'
            }`}>
            {d === 1 ? '24h' : `${d}d`}
          </button>
        ))}
      </div>

      {/* Template cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {templates.map(t => (
          <button key={t.key} onClick={() => run(t.key)}
            className={`text-left rounded-xl border p-5 transition-all hover:shadow-md ${t.color} ${
              activeRpt === t.key ? 'ring-2 ring-blue-400' : ''
            }`}>
            <t.icon size={22} className="mb-2" />
            <div className="font-semibold text-sm">{t.label}</div>
            <div className="text-xs mt-1 opacity-70">{t.desc}</div>
            {loading === t.key && (
              <div className="mt-2 flex items-center gap-1.5 text-xs">
                <Spinner size={12} /> Generating...
              </div>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      {/* Results */}
      {data && activeRpt && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <h2 className="font-semibold text-sm text-gray-800">
              {templates.find(t => t.key === activeRpt)?.label} -- Last {days} day{days > 1 ? 's' : ''}
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">
                {(data as { channel_count?: number }).channel_count ?? (data as { data?: unknown[] }).data?.length ?? 0} channels
              </span>
            </div>
          </div>

          <div className="overflow-auto max-h-96">
            <ReportTable reportKey={activeRpt} rows={(data as { data?: unknown[] }).data ?? []} />
          </div>
        </div>
      )}
    </div>
  )
}

function ReportTable({ reportKey, rows }: { reportKey: string; rows: unknown[] }) {
  if (rows.length === 0) return (
    <div className="py-10 text-center text-gray-400 text-sm">No data for this period</div>
  )

  if (reportKey === 'uptime') {
    const r = rows as Array<{ channel: string; group: string; status: string; uptime_pct: number; total_checks: number; total_errors: number }>
    return (
      <table className="w-full text-sm">
        <thead><tr className="bg-gray-50 border-b border-gray-100">
          {['Channel','Group','Status','Uptime %','Checks','Errors'].map(h => (
            <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500">{h}</th>
          ))}
        </tr></thead>
        <tbody className="divide-y divide-gray-50">
          {r.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="px-4 py-2.5 font-medium text-gray-900">{row.channel}</td>
              <td className="px-4 py-2.5 text-gray-500">{row.group}</td>
              <td className="px-4 py-2.5"><StatusPill status={row.status} /></td>
              <td className="px-4 py-2.5">
                <span className={row.uptime_pct >= 99 ? 'text-green-600 font-semibold' : row.uptime_pct >= 90 ? 'text-amber-600' : 'text-red-600 font-semibold'}>
                  {row.uptime_pct.toFixed(1)}%
                </span>
              </td>
              <td className="px-4 py-2.5 text-gray-600">{row.total_checks}</td>
              <td className="px-4 py-2.5 text-gray-600">{row.total_errors}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  if (reportKey === 'errors') {
    const r = rows as Array<{ error_type: string; severity: string; count: number }>
    return (
      <table className="w-full text-sm">
        <thead><tr className="bg-gray-50 border-b border-gray-100">
          {['Error Type','Severity','Count'].map(h => (
            <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500">{h}</th>
          ))}
        </tr></thead>
        <tbody className="divide-y divide-gray-50">
          {r.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="px-4 py-2.5 font-mono text-gray-800">{row.error_type}</td>
              <td className="px-4 py-2.5"><SeverityPill s={row.severity} /></td>
              <td className="px-4 py-2.5 font-bold text-gray-900">{row.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  if (reportKey === 'bitrate') {
    const r = rows as Array<{ channel: string; group: string; avg_bitrate: number | null; expected: number | null; avg_latency_ms: number | null }>
    return (
      <table className="w-full text-sm">
        <thead><tr className="bg-gray-50 border-b border-gray-100">
          {['Channel','Group','Avg Bitrate','Expected','Avg Latency'].map(h => (
            <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500">{h}</th>
          ))}
        </tr></thead>
        <tbody className="divide-y divide-gray-50">
          {r.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="px-4 py-2.5 font-medium text-gray-900">{row.channel}</td>
              <td className="px-4 py-2.5 text-gray-500">{row.group}</td>
              <td className="px-4 py-2.5 font-mono">{formatBitrate(row.avg_bitrate)}</td>
              <td className="px-4 py-2.5 font-mono text-gray-400">{formatBitrate(row.expected)}</td>
              <td className="px-4 py-2.5 font-mono">{row.avg_latency_ms ? `${row.avg_latency_ms}ms` : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }
  return null
}

// ---- Custom Report ------------------------------------------------------------
function CustomTab() {
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 7)
    return d.toISOString().slice(0, 16)
  })
  const [endDate,    setEndDate]    = useState(() => new Date().toISOString().slice(0, 16))
  const [loading,    setLoading]    = useState(false)
  const [csvLoading, setCsvLoading] = useState(false)
  const [xlsxLoading,setXlsxLoading]= useState(false)
  const [report,     setReport]     = useState<Record<string, unknown> | null>(null)
  const [error,      setError]      = useState('')

  const payload = {
    start_time: new Date(startDate).toISOString(),
    end_time:   new Date(endDate).toISOString(),
    include_metrics: true,
    include_errors:  true,
  }

  const errMsg = (e: unknown, fb: string) => {
    if (!axios.isAxiosError(e)) return fb
    const d = e.response?.data?.detail
    if (typeof d === 'string') return d
    return e.message || fb
  }

  const handleGenerate = async () => {
    if (!startDate || !endDate) return setError('Both dates required')
    if (new Date(startDate) >= new Date(endDate)) return setError('End must be after start')
    setLoading(true); setError('')
    try { setReport(await generateReport(payload)) }
    catch (e) { setError(errMsg(e, 'Failed to generate report')) }
    finally { setLoading(false) }
  }

  const handleCsv = async () => {
    setCsvLoading(true)
    try { await downloadCsvReport(payload) }
    catch (e) { setError(errMsg(e, 'CSV export failed')) }
    finally { setCsvLoading(false) }
  }

  const handleXlsx = async () => {
    setXlsxLoading(true)
    try {
      const res  = await axios.post('/api/v1/reports/export/xlsx', payload, {
        responseType: 'blob',
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
      })
      const url  = URL.createObjectURL(res.data)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `ott_report_${Date.now()}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) { setError(errMsg(e, 'XLSX export failed')) }
    finally { setXlsxLoading(false) }
  }

  type Row = { channel_name: string; group: string | null; availability_pct: number; avg_bitrate_kbps: number | null; avg_response_time_ms: number | null; total_errors: number }
  const rows = (report?.data as Row[]) ?? []

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-sm text-gray-700 mb-4">Report Configuration</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Start</label>
            <input type="datetime-local" className="input" value={startDate} onChange={e => setStartDate(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">End</label>
            <input type="datetime-local" className="input" value={endDate} onChange={e => setEndDate(e.target.value)} />
          </div>
        </div>
        {error && <p className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
        <div className="flex flex-wrap gap-3 mt-4">
          <button className="btn-primary" onClick={handleGenerate} disabled={loading}>
            {loading ? <><Spinner size={14} className="text-white" /> Generating...</> : <><PlayCircle size={14} /> Generate</>}
          </button>
          <button className="btn-secondary" onClick={handleCsv} disabled={csvLoading}>
            {csvLoading ? <Spinner size={14} /> : <FileDown size={14} />} CSV
          </button>
          <button className="btn-secondary" onClick={handleXlsx} disabled={xlsxLoading}>
            {xlsxLoading ? <Spinner size={14} /> : <FileDown size={14} />} Excel
          </button>
        </div>
      </div>

      {rows.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
            <h2 className="font-semibold text-sm text-gray-800">Results</h2>
            <span className="text-xs text-gray-400">{rows.length} channels</span>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead><tr className="bg-gray-50 border-b border-gray-100">
                {['Channel','Group','Uptime %','Avg Bitrate','Avg Latency','Errors'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500">{h}</th>
                ))}
              </tr></thead>
              <tbody className="divide-y divide-gray-50">
                {rows.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5 font-medium text-gray-900">{r.channel_name}</td>
                    <td className="px-4 py-2.5 text-gray-500">{r.group ?? '-'}</td>
                    <td className="px-4 py-2.5">
                      <span className={r.availability_pct >= 99 ? 'text-green-600 font-semibold' : r.availability_pct >= 90 ? 'text-amber-600' : 'text-red-600 font-semibold'}>
                        {r.availability_pct?.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-gray-700">{formatBitrate(r.avg_bitrate_kbps)}</td>
                    <td className="px-4 py-2.5 font-mono text-gray-700">{r.avg_response_time_ms ? `${r.avg_response_time_ms}ms` : '-'}</td>
                    <td className="px-4 py-2.5 text-gray-700">{r.total_errors}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ---- Stream Diagnostics -------------------------------------------------------
function DiagnosticTab() {
  const [url,      setUrl]      = useState('')
  const [loading,  setLoading]  = useState(false)
  const [result,   setResult]   = useState<Record<string, unknown> | null>(null)
  const [error,    setError]    = useState('')

  const run = async () => {
    if (!url.trim()) return setError('Enter a stream URL')
    setLoading(true); setError(''); setResult(null)
    try {
      const res = await apiV2.get(`/reports/stream-check?url=${encodeURIComponent(url)}`)
      setResult(res.data)
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Request failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-sm text-gray-800 mb-3">Why is my stream not connecting?</h2>
        <p className="text-sm text-gray-500 mb-4">
          Enter the stream URL you added to the system. This tool explains the most common
          reasons a stream might fail to connect from the monitoring workers.
        </p>
        <div className="flex gap-3">
          <input
            className="input flex-1"
            placeholder="http://192.168.1.100:8080/live/stream.m3u8"
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
          />
          <button className="btn-primary" onClick={run} disabled={loading}>
            {loading ? <Spinner size={14} /> : <Search size={14} />} Check
          </button>
        </div>
        {error && <p className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
      </div>

      {result && (
        <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
          <div className="px-5 py-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">URL Checked</p>
            <p className="font-mono text-sm text-gray-800 mt-1 break-all">{result.url as string}</p>
          </div>

          <div className="px-5 py-4">
            <p className="text-xs font-semibold text-amber-600 uppercase tracking-wide mb-2">Possible Reasons for Failure</p>
            {(result.reasons_stream_may_fail as string[]).map((r, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <span className="text-amber-500 mt-0.5 flex-shrink-0">!</span>
                <p className="text-sm text-gray-700">{r}</p>
              </div>
            ))}
          </div>

          <div className="px-5 py-4">
            <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-2">Suggestions</p>
            {(result.suggestions as string[]).map((s, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <span className="text-blue-500 mt-0.5 flex-shrink-0">-</span>
                <p className="text-sm text-gray-700">{s}</p>
              </div>
            ))}
          </div>

          <div className="px-5 py-4 bg-gray-50 rounded-b-xl">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Manual Test Command</p>
            <code className="block text-xs font-mono bg-white border border-gray-200 rounded p-3 text-gray-800 break-all">
              {result.manual_test as string}
            </code>
            <p className="text-xs text-gray-400 mt-2">
              Run this on the server to test stream reachability from inside the worker container.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// ---- Shared small components --------------------------------------------------
function StatusPill({ status }: { status: string }) {
  const c: Record<string, string> = {
    UP: 'bg-green-100 text-green-700',
    DOWN: 'bg-red-100 text-red-700',
    ERROR: 'bg-amber-100 text-amber-700',
    WARNING: 'bg-purple-100 text-purple-700',
    UNKNOWN: 'bg-gray-100 text-gray-600',
  }
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${c[status] ?? c.UNKNOWN}`}>{status}</span>
}
function SeverityPill({ s }: { s: string }) {
  const c: Record<string, string> = {
    CRITICAL: 'bg-red-100 text-red-700',
    MAJOR: 'bg-amber-100 text-amber-700',
    WARNING: 'bg-purple-100 text-purple-700',
    INFO: 'bg-blue-100 text-blue-700',
  }
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${c[s] ?? 'bg-gray-100 text-gray-600'}`}>{s}</span>
}
