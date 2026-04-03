import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Search, RefreshCw, Trash2 } from 'lucide-react'
import { useChannels, useDeleteChannel } from '@/hooks/useApi'
import {
  PageHeader, PageLoader, ErrorDisplay, StatusBadge, EmptyState
} from '@/components/common'
import { formatBitrate, formatRelativeTime } from '@/utils'
import type { ChannelStatus } from '@/types'
import AddChannelModal from '@/components/channels/AddChannelModal'

const STATUS_FILTERS: (ChannelStatus | 'ALL')[] = ['ALL', 'UP', 'DOWN', 'ERROR', 'WARNING', 'UNKNOWN']

export default function ChannelsPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<ChannelStatus | 'ALL'>('ALL')
  const [page, setPage] = useState(1)
  const [showAdd, setShowAdd] = useState(false)

  const { data, isLoading, error, refetch } = useChannels({
    search: search || undefined,
    status: statusFilter !== 'ALL' ? statusFilter : undefined,
    page,
    per_page: 50,
  })
  const deleteMutation = useDeleteChannel()

  const handleDelete = async (id: string, name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`Delete channel "${name}"? This cannot be undone.`)) return
    await deleteMutation.mutateAsync(id)
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Channels"
        subtitle={`${data?.total ?? 0} registered streams`}
        actions={
          <>
            <button className="btn-secondary" onClick={() => refetch()}>
              <RefreshCw size={14} /> Refresh
            </button>
            <button className="btn-primary" onClick={() => setShowAdd(true)}>
              <Plus size={14} /> Add Channel
            </button>
          </>
        }
      />

      <div className="flex-1 overflow-auto p-6">
        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="relative flex-1 min-w-48">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              className="input pl-8"
              placeholder="Search channels…"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
            />
          </div>
          <div className="flex gap-1">
            {STATUS_FILTERS.map(s => (
              <button
                key={s}
                onClick={() => { setStatusFilter(s); setPage(1) }}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  statusFilter === s
                    ? 'bg-blue-600 text-white'
                    : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        {isLoading ? (
          <PageLoader />
        ) : error ? (
          <ErrorDisplay message="Failed to load channels." />
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase">Name</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase">Group</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase">Protocol</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase">Bitrate</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase">Resolution</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase">Last Checked</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data?.items.length === 0 ? (
                  <tr>
                    <td colSpan={8}>
                      <EmptyState message="No channels found. Add one to get started." />
                    </td>
                  </tr>
                ) : (
                  data?.items.map(ch => (
                    <tr
                      key={ch.id}
                      className="table-row-hover"
                      onClick={() => navigate(`/channels/${ch.id}`)}
                    >
                      <td className="px-4 py-3">
                        <StatusBadge status={ch.status} />
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900 max-w-48 truncate">
                        {ch.name}
                      </td>
                      <td className="px-4 py-3 text-gray-500">{ch.group ?? '—'}</td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                          {ch.protocol}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-gray-700">
                        {formatBitrate(ch.expected_bitrate)}
                      </td>
                      <td className="px-4 py-3 font-mono text-gray-700">
                        {ch.expected_resolution ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-400 text-xs">
                        {formatRelativeTime(ch.last_checked_at)}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          className="p-1.5 text-gray-400 hover:text-red-500 transition-colors rounded"
                          onClick={e => handleDelete(ch.id, ch.name, e)}
                          title="Delete channel"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {/* Pagination */}
            {data && data.total > data.per_page && (
              <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-500">
                <span>
                  Showing {(page - 1) * data.per_page + 1}–
                  {Math.min(page * data.per_page, data.total)} of {data.total}
                </span>
                <div className="flex gap-2">
                  <button
                    className="btn-secondary py-1 px-3 text-xs"
                    disabled={page === 1}
                    onClick={() => setPage(p => p - 1)}
                  >
                    Previous
                  </button>
                  <button
                    className="btn-secondary py-1 px-3 text-xs"
                    disabled={page * data.per_page >= data.total}
                    onClick={() => setPage(p => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {showAdd && <AddChannelModal onClose={() => setShowAdd(false)} />}
    </div>
  )
}
