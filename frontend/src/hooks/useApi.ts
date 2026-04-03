import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '@/services/api'

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const useDashboardSummary = () =>
  useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: api.fetchDashboardSummary,
    refetchInterval: 10_000,
  })

export const useDashboardChannels = () =>
  useQuery({
    queryKey: ['dashboard', 'channels'],
    queryFn: api.fetchDashboardChannels,
    refetchInterval: 15_000,
  })

// ── Channels ──────────────────────────────────────────────────────────────────
export const useChannels = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: ['channels', params],
    queryFn: () => api.fetchChannels(params),
    refetchInterval: 30_000,
  })

export const useChannel = (id: string) =>
  useQuery({
    queryKey: ['channels', id],
    queryFn: () => api.fetchChannel(id),
    enabled: !!id,
  })

export const useCreateChannel = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.createChannel,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['channels'] }),
  })
}

export const useUpdateChannel = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: unknown }) =>
      api.updateChannel(id, data as never),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['channels'] }),
  })
}

export const useDeleteChannel = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteChannel,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['channels'] }),
  })
}

// ── Metrics ───────────────────────────────────────────────────────────────────
export const useChannelMetrics = (id: string, hours = 24) =>
  useQuery({
    queryKey: ['metrics', id, hours],
    queryFn: () => api.fetchChannelMetrics(id, hours),
    enabled: !!id,
    refetchInterval: 30_000,
  })

export const useMetricSummary = (id: string, hours = 24) =>
  useQuery({
    queryKey: ['metrics-summary', id, hours],
    queryFn: () => api.fetchMetricSummary(id, hours),
    enabled: !!id,
    refetchInterval: 30_000,
  })

// ── Errors ────────────────────────────────────────────────────────────────────
export const useChannelErrors = (id: string, hours = 24) =>
  useQuery({
    queryKey: ['errors', id, hours],
    queryFn: () => api.fetchChannelErrors(id, hours),
    enabled: !!id,
    refetchInterval: 30_000,
  })

// ── Alerts ────────────────────────────────────────────────────────────────────
export const useAlerts = (params?: Record<string, unknown>) =>
  useQuery({
    queryKey: ['alerts', params],
    queryFn: () => api.fetchAlerts(params),
    refetchInterval: 15_000,
  })

export const useAcknowledgeAlert = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, by }: { id: string; by: string }) => api.acknowledgeAlert(id, by),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
}

export const useResolveAlert = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.resolveAlert,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
}

// ── Health ────────────────────────────────────────────────────────────────────
export const useHealth = () =>
  useQuery({
    queryKey: ['health'],
    queryFn: api.fetchHealth,
    refetchInterval: 30_000,
  })
