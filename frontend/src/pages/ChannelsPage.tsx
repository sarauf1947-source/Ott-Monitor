// frontend/src/pages/ChannelsPage.tsx  (v2.3)
// New features:
//   - Checkbox multi-select with bulk delete toolbar
//   - CSV import button (parses name,stream_url,protocol,group,description)
//   - Group By toggle that collapses rows by channel.group
import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus, Search, RefreshCw, Trash2, Upload, Layers, List as ListIcon, CheckSquare,
} from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useChannels, useDeleteChannel } from '@/hooks/useApi'
import { apiV2 } from '@/services/apiV2'
import {
  PageHeader, PageLoader, ErrorDisplay, StatusBadge, EmptyState,
} from '@/components/common'
import { formatBitrate, formatRelativeTime, cn } from '@/utils'
import type { Channel, ChannelStatus } from '@/types'
import AddChannelModal from '@/components/channels/AddChannelModal'

const STATUS_FILTERS: (ChannelStatus | 'ALL')[] = ['ALL', 'UP', 'DOWN', 'ERROR', 'WARNING', 'UNKNOWN']

export default function ChannelsPage() {
  const navigate = useNavigate()
  const qc       = useQueryClient()

  const [search,       setSearch]       = useState('')
  const [statusFilter, setStatusFilter] = useState<ChannelStatus | 'ALL'>('ALL')
  const [page,         setPage]         = useState(1)
  const [showAdd,      setShowAdd]      = useState(false)
  const [groupBy,      setGroupBy]      = useState(false)
  const [selected,     setSelected]     = useState<Set<string>>(new Set<string>())
  const [importing,    setImporting]    = useState(false)
  const [importMsg,    setImportMsg]    = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const { data, isLoading, error, refetch } = useChannels({
    search:     search || undefined,
    status:     statusFilter !== 'ALL' ? statusFilter : undefined,
    page,
    per_page:   200,  // load more when grouping
  })
  const deleteSingle = useDeleteChannel()

  // Bulk delete mutation
  const bulkDelete = useMutation({
    mutationFn: async (ids: string[]) => {
      await Promise.all(ids.map(id => apiV2.delete(`/channels/${id}`)))
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['channels'] })
      setSelected(new Set<string>())
    },
  })

  const handleDeleteSingle = async (id: string, name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return
    await deleteSingle.mutateAsync(id)
  }

  const handleBulkDelete = async () => {
    if (!confirm(`Delete ${selected.size} channel(s)? This cannot be undone.`)) return
    await bulkDelete.mutateAsync(Array.from(selected))
  }

  const toggleRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setSelected(prev => {
      const next = new Set<string>(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    const ids = (data?.items ?? []).map(c => c.id)
    if (selected.size === ids.length) {
      setSelected(new Set<string>())
    } else {
      setSelected(new Set<string>(ids))
    }
  }

  // CSV import
  const handleCsvFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true); setImportMsg('')
    try {
      const text  = await file.text()
      const lines = text.split('\n').filter(l => l.trim())
      const header = lines[0].toLowerCase().split(',').map(h => h.trim())
      const nameIdx  = header.indexOf('name')
      const urlIdx   = header.indexOf('stream_url')
      if (nameIdx === -1 || urlIdx === -1) {
        setImportMsg('CSV must have "name" and "stream_url" columns in the header row')
        return
      }
      const protoIdx = header.indexOf('protocol')
      const groupIdx = header.indexOf('group')
      const descIdx  = header.indexOf('description')

      let imported = 0; let failed = 0
      for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(',').map(c => c.trim())
        const name = cols[nameIdx]; const url = cols[urlIdx]
        if (!name || !url) { failed++; continue }
        try {
          await apiV2.post('/channels', {
            name,
            stream_url:  url,
            protocol:    protoIdx !== -1 ? (cols[protoIdx] || 'HLS') : 'HLS',
            group:       groupIdx !== -1 ? (cols[groupIdx] || null)  : null,
            description: descIdx  !== -1 ? (cols[descIdx]  || null)  : null,
          })
          imported++
        } catch { failed++ }
      }
      qc.invalidateQueries({ queryKey: ['channels'] })
      setImportMsg(`Imported ${imported} channel(s)${failed > 0 ? `, ${failed} failed` : ''}`)
    } catch {
      setImportMsg('Failed to read CSV file')
    } finally {
      setImporting(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const items = data?.items ?? []

  // Group channels by their group field
  const grouped = groupBy
    ? items.reduce<Record<string, typeof items>>((acc, ch) => {
        const key = ch.group ?? '(No Group)'
        if (!acc[key]) acc[key] = []
        acc[key].push(ch)
        return acc
      }, {})
    : null

  const allSelected = items.length > 0 && selected.size === items.length

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Channels"
        subtitle={`${data?.total ?? 0} registered streams`}
        actions={
          <div className="flex items-center gap-2">
            <button className="btn-secondary" onClick={() => refetch()}>
              <RefreshCw size={14} /> Refresh
            </button>
            {/* CSV import */}
            <button
              className="btn-secondary"
              onClick={() => fileRef.current?.click()}
              disabled={importing}
              title="Import channels from CSV">
              <Upload size={14} />
              {importing ? 'Importing...' : 'Import CSV'}
            </button>
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleCsvFile} />
            {/* Group toggle */}
            <button
              className={cn('btn-secondary', groupBy && 'bg-blue-50 text-blue-700 border-blue-300')}
              onClick={() => setGroupBy(g => !g)}
              title={groupBy ? 'List view' : 'Group by category'}>
              {groupBy ? <ListIcon size={14} /> : <Layers size={14} />}
              {groupBy ? 'List' : 'Group'}
            </button>
            <button className="btn-primary" onClick={() => setShowAdd(true)}>
              <Plus size={14} /> Add Channel
            </button>
          </div>
        }
      />

      <div className="flex-1 overflow-auto p-6">
        {/* Import message */}
        {importMsg && (
          <div className={cn(
            'mb-4 px-4 py-3 rounded-lg text-sm border',
            importMsg.includes('failed') || importMsg.startsWith('Failed') || importMsg.startsWith('CSV')
              ? 'bg-red-50 text-red-700 border-red-200'
              : 'bg-green-50 text-green-700 border-green-200'
          )}>
            {importMsg}
            <button onClick={() => setImportMsg('')} className="ml-3 text-xs underline">dismiss</button>
          </div>
        )}

        {/* Bulk delete toolbar */}
        {selected.size > 0 && (
          <div className="mb-4 flex items-center gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-2.5">
            <CheckSquare size={16} className="text-red-600" />
            <span className="text-sm font-medium text-red-800">{selected.size} channel(s) selected</span>
            <button
              onClick={handleBulkDelete}
              disabled={bulkDelete.isPending}
              className="ml-auto flex items-center gap-1.5 px-4 py-1.5 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              <Trash2 size={13} />
              {bulkDelete.isPending ? 'Deleting...' : 'Delete Selected'}
            </button>
            <button
              onClick={() => setSelected(new Set<string>())}
              className="px-3 py-1.5 bg-white border border-gray-200 text-gray-600 rounded-lg text-sm">
              Cancel
            </button>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="relative flex-1 min-w-48">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              className="input pl-8"
              placeholder="Search channels..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
            />
          </div>
          <div className="flex gap-1">
            {STATUS_FILTERS.map(s => (
              <button key={s}
                onClick={() => { setStatusFilter(s); setPage(1) }}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                  statusFilter === s
                    ? 'bg-blue-600 text-white'
                    : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
                )}>
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* CSV format hint */}
        <p className="text-xs text-gray-400 mb-3">
          CSV import format: <code className="bg-gray-100 px-1 rounded">name,stream_url,protocol,group,description</code>
          (header row required; protocol defaults to HLS)
        </p>

        {isLoading ? (
          <PageLoader />
        ) : error ? (
          <ErrorDisplay message="Failed to load channels." />
        ) : groupBy && grouped ? (
          // ---- Grouped view ----
          <div className="space-y-4">
            {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([grp, chans]) => (
              <div key={grp} className="card overflow-hidden">
                <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                  <span className="font-semibold text-sm text-gray-700">{grp}</span>
                  <span className="text-xs text-gray-400">{chans.length} channels</span>
                </div>
                <ChannelTable
                  channels={chans}
                  selected={selected}
                  allSelected={allSelected}
                  onToggleRow={toggleRow}
                  onToggleAll={toggleAll}
                  onDelete={handleDeleteSingle}
                  onNavigate={id => navigate(`/channels/${id}`)}
                />
              </div>
            ))}
          </div>
        ) : (
          // ---- Flat list view ----
          <div className="card overflow-hidden">
            <ChannelTable
              channels={items}
              selected={selected}
              allSelected={allSelected}
              onToggleRow={toggleRow}
              onToggleAll={toggleAll}
              onDelete={handleDeleteSingle}
              onNavigate={id => navigate(`/channels/${id}`)}
            />
            {data && data.total > data.per_page && (
              <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-500">
                <span>Showing {(page - 1) * data.per_page + 1}-{Math.min(page * data.per_page, data.total)} of {data.total}</span>
                <div className="flex gap-2">
                  <button className="btn-secondary py-1 px-3 text-xs" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
                  <button className="btn-secondary py-1 px-3 text-xs" disabled={page * data.per_page >= data.total} onClick={() => setPage(p => p + 1)}>Next</button>
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

// ---- Shared table component -------------------------------------------------
function ChannelTable({
  channels, selected, allSelected, onToggleRow, onToggleAll, onDelete, onNavigate,
}: {
  channels: Channel[]
  selected: Set<string>
  allSelected: boolean
  onToggleRow: (id: string, e: React.MouseEvent) => void
  onToggleAll: () => void
  onDelete: (id: string, name: string, e: React.MouseEvent) => void
  onNavigate: (id: string) => void
}) {
  if (!channels || channels.length === 0) {
    return (
      <table className="w-full">
        <tbody><tr><td><EmptyState message="No channels found. Add one to get started." /></td></tr></tbody>
      </table>
    )
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="bg-gray-50 border-b border-gray-200">
          <th className="px-3 py-3 w-8">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={onToggleAll}
              className="rounded border-gray-300"
              onClick={e => e.stopPropagation()}
            />
          </th>
          {['Status','Name','Group','Protocol','Bitrate','Resolution','Last Checked',''].map(h => (
            <th key={h} className="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-100">
        {channels.map(ch => (
          <tr
            key={ch.id}
            className={cn('table-row-hover cursor-pointer', selected.has(ch.id) && 'bg-blue-50')}
            onClick={() => onNavigate(ch.id)}
          >
            <td className="px-3 py-3" onClick={e => onToggleRow(ch.id, e)}>
              <input
                type="checkbox"
                checked={selected.has(ch.id)}
                onChange={() => {}}
                className="rounded border-gray-300"
              />
            </td>
            <td className="px-4 py-3"><StatusBadge status={ch.status} /></td>
            <td className="px-4 py-3 font-medium text-gray-900 max-w-48 truncate">{ch.name}</td>
            <td className="px-4 py-3 text-gray-500">{ch.group ?? '-'}</td>
            <td className="px-4 py-3">
              <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">{ch.protocol}</span>
            </td>
            <td className="px-4 py-3 font-mono text-gray-700">{formatBitrate(ch.expected_bitrate)}</td>
            <td className="px-4 py-3 font-mono text-gray-700">{ch.expected_resolution ?? '-'}</td>
            <td className="px-4 py-3 text-gray-400 text-xs">{formatRelativeTime(ch.last_checked_at)}</td>
            <td className="px-4 py-3">
              <button
                className="p-1.5 text-gray-400 hover:text-red-500 transition-colors rounded"
                onClick={e => onDelete(ch.id, ch.name, e)}
                title="Delete">
                <Trash2 size={14} />
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
