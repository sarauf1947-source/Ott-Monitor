import { useState } from 'react'
import { FileDown, PlayCircle } from 'lucide-react'
import axios from 'axios'
import { generateReport, downloadCsvReport } from '@/services/api'
import { PageHeader, Spinner } from '@/components/common'
import { formatBitrate } from '@/utils'

export default function ReportsPage() {
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 7)
    return d.toISOString().slice(0, 16)
  })
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 16))
  const [loading, setLoading] = useState(false)
  const [csvLoading, setCsvLoading] = useState(false)
  const [report, setReport] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')

  const payload = {
    start_time: new Date(startDate).toISOString(),
    end_time: new Date(endDate).toISOString(),
    include_metrics: true,
    include_errors: true,
  }

  const getApiErrorMessage = (err: unknown, fallback: string) => {
    if (!axios.isAxiosError(err)) return fallback

    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail

    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      if (typeof first?.msg === 'string' && first.msg.trim()) return first.msg
    }

    const backendError = err.response?.data?.error
    if (typeof backendError === 'string' && backendError.trim()) return backendError

    if (typeof err.message === 'string' && err.message.trim()) return err.message

    return fallback
  }

  const handleGenerate = async () => {
    if (!startDate || !endDate) {
      setError('Start and end date/time are required.')
      return
    }

    if (new Date(startDate) >= new Date(endDate)) {
      setError('End date/time must be later than start date/time.')
      return
    }

    setLoading(true); setError('')
    try {
      const data = await generateReport(payload)
      setReport(data)
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to generate report.'))
    } finally {
      setLoading(false)
    }
  }

  const handleCsv = async () => {
    if (!startDate || !endDate) {
      setError('Start and end date/time are required.')
      return
    }

    if (new Date(startDate) >= new Date(endDate)) {
      setError('End date/time must be later than start date/time.')
      return
    }

    setError('')
    setCsvLoading(true)
    try { await downloadCsvReport(payload) }
    catch (err) { setError(getApiErrorMessage(err, 'CSV export failed.')) }
    finally { setCsvLoading(false) }
  }

  type ReportRow = {
    channel_name: string
    group: string | null
    availability_pct: number
    avg_bitrate_kbps: number | null
    avg_response_time_ms: number | null
    total_errors: number
  }

  const rows = (report?.data as ReportRow[]) ?? []

  return (
    <div className="flex flex-col h-full">
      <PageHeader title="Reports" subtitle="Generate availability and quality reports per channel" />

      <div className="flex-1 overflow-auto p-6 space-y-5">
        {/* Controls */}
        <div className="card p-5">
          <h2 className="font-semibold text-sm text-gray-700 mb-4">Report Configuration</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Start Date / Time</label>
              <input
                type="datetime-local"
                className="input"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">End Date / Time</label>
              <input
                type="datetime-local"
                className="input"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
              />
            </div>
          </div>
          {error && (
            <p className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
          )}
          <div className="flex gap-3 mt-4">
            <button
              className="btn-primary"
              onClick={handleGenerate}
              disabled={loading}
            >
              {loading ? <Spinner size={14} className="text-white" /> : <PlayCircle size={14} />}
              {loading ? 'Generating…' : 'Generate Report'}
            </button>
            <button
              className="btn-secondary"
              onClick={handleCsv}
              disabled={csvLoading}
            >
              {csvLoading ? <Spinner size={14} /> : <FileDown size={14} />}
              Export CSV
            </button>
          </div>
        </div>

        {/* Results */}
        {report && (
          <div className="card overflow-hidden">
            <div className="card-header">
              <span className="font-semibold text-sm text-gray-700">
                Report Results — {rows.length} channels
              </span>
              <span className="text-xs text-gray-400">
                Period: {new Date(startDate).toLocaleDateString()} – {new Date(endDate).toLocaleDateString()}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Channel</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Group</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Availability</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Avg Bitrate</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Avg Latency</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Total Errors</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5 font-medium text-gray-900">{row.channel_name}</td>
                      <td className="px-4 py-2.5 text-gray-500">{row.group ?? '—'}</td>
                      <td className="px-4 py-2.5">
                        <span className={
                          (row.availability_pct ?? 0) >= 99 ? 'text-green-600 font-semibold' :
                          (row.availability_pct ?? 0) >= 95 ? 'text-amber-600 font-semibold' :
                          'text-red-600 font-semibold'
                        }>
                          {row.availability_pct != null ? `${row.availability_pct.toFixed(1)}%` : '—'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-gray-700">
                        {formatBitrate(row.avg_bitrate_kbps)}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-gray-700">
                        {row.avg_response_time_ms != null ? `${row.avg_response_time_ms}ms` : '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={row.total_errors > 0 ? 'text-red-600 font-semibold' : 'text-gray-400'}>
                          {row.total_errors}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
