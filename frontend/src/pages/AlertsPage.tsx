import { useState } from 'react'
import { useAlerts, useAcknowledgeAlert, useResolveAlert } from '@/hooks/useApi'
import {
  PageHeader, PageLoader, ErrorDisplay, SeverityBadge, EmptyState
} from '@/components/common'
import { formatDateTime, cn } from '@/utils'
import type { AlertStatus } from '@/types'

const STATUS_TABS: (AlertStatus | 'ALL')[] = ['ALL', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED']

export default function AlertsPage() {
  const [statusFilter, setStatusFilter] = useState<AlertStatus | 'ALL'>('OPEN')
  const { data, isLoading, error } = useAlerts({
    status: statusFilter !== 'ALL' ? statusFilter : undefined,
    limit: 200,
  })
  const acknowledge = useAcknowledgeAlert()
  const resolve = useResolveAlert()

  const handleAck = async (id: string) => {
    const by = prompt('Your name / operator ID:')
    if (!by) return
    await acknowledge.mutateAsync({ id, by })
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Alerts"
        subtitle={`${data?.total ?? 0} ${statusFilter === 'ALL' ? 'total' : statusFilter.toLowerCase()} alerts`}
      />

      <div className="flex-1 overflow-auto p-6">
        {/* Filter tabs */}
        <div className="flex gap-1 mb-4">
          {STATUS_TABS.map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                statusFilter === s
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {isLoading ? (
          <PageLoader />
        ) : error ? (
          <ErrorDisplay message="Failed to load alerts." />
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Severity</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Channel</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Message</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Triggered</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data?.items.length === 0 ? (
                  <tr>
                    <td colSpan={7}>
                      <EmptyState message="No alerts in this category." />
                    </td>
                  </tr>
                ) : (
                  data?.items.map(alert => (
                    <tr
                      key={alert.id}
                      className={cn(
                        'transition-colors',
                        alert.status === 'OPEN' && alert.severity === 'CRITICAL' ? 'bg-red-50' :
                        alert.status === 'OPEN' ? 'bg-amber-50' : ''
                      )}
                    >
                      <td className="px-4 py-3">
                        <SeverityBadge severity={alert.severity} />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-700">{alert.alert_type}</td>
                      <td className="px-4 py-3 text-xs text-gray-500 font-mono truncate max-w-32">
                        {alert.channel_id.slice(0, 8)}…
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-600 max-w-xs truncate">
                        {alert.message ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                        {formatDateTime(alert.triggered_at)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          'text-xs font-semibold px-2 py-0.5 rounded-full',
                          alert.status === 'OPEN'           ? 'bg-red-100 text-red-700' :
                          alert.status === 'ACKNOWLEDGED'   ? 'bg-amber-100 text-amber-700' :
                                                              'bg-green-100 text-green-700'
                        )}>
                          {alert.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          {alert.status === 'OPEN' && (
                            <button
                              className="text-xs text-blue-600 hover:underline"
                              onClick={() => handleAck(alert.id)}
                            >
                              Ack
                            </button>
                          )}
                          {alert.status !== 'RESOLVED' && (
                            <button
                              className="text-xs text-green-600 hover:underline"
                              onClick={() => resolve.mutateAsync(alert.id)}
                            >
                              Resolve
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
