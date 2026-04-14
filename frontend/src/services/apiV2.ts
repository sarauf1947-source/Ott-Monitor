// frontend/src/services/apiV2.ts  (v2.2 - complete)
import axios from 'axios'

export const apiV2 = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
})

apiV2.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiV2.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('ott_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// Auth
export interface UserResponse {
  id: number; username: string; email: string; full_name: string | null
  role: string; is_active: boolean; created_at: string; last_login: string | null
}
export interface UserCreate {
  username: string; email: string; password: string
  full_name?: string; role?: string; is_active?: boolean
}
export interface UserUpdate {
  email?: string; full_name?: string; role?: string; is_active?: boolean
}
export const listUsers         = () => apiV2.get<UserResponse[]>('/users/').then(r => r.data)
export const createUser        = (p: UserCreate) => apiV2.post<UserResponse>('/users/', p).then(r => r.data)
export const updateUser        = (id: number, p: UserUpdate) => apiV2.patch<UserResponse>(`/users/${id}`, p).then(r => r.data)
export const deleteUser        = (id: number) => apiV2.delete(`/users/${id}`)
export const resetUserPassword = (id: number, new_password: string) => apiV2.post(`/users/${id}/reset-password`, { new_password })

// Settings
export const getSmtp            = () => apiV2.get('/settings/smtp').then(r => r.data)
export const saveSmtp           = (d: object) => apiV2.put('/settings/smtp', d).then(r => r.data)
export const testSmtp           = (to_email: string) => apiV2.post('/settings/smtp/test', { to_email }).then(r => r.data)
export const getWebhooks        = () => apiV2.get('/settings/webhooks').then(r => r.data)
export const addWebhook         = (d: object) => apiV2.post('/settings/webhooks', d).then(r => r.data)
export const removeWebhook      = (id: string) => apiV2.delete(`/settings/webhooks/${id}`)
export const testWebhook        = (d: { webhook_id?: string; url?: string; name?: string }) => apiV2.post('/settings/webhooks/test', d).then(r => r.data)
export const getAlertConfig     = () => apiV2.get('/settings/alerts').then(r => r.data)
export const saveAlertConfig    = (d: object) => apiV2.put('/settings/alerts', d).then(r => r.data)
export const getNotifications   = () => apiV2.get('/settings/notifications').then(r => r.data)
export const saveNotifications  = (d: object) => apiV2.put('/settings/notifications', d).then(r => r.data)

// System metrics
export const getSystemMetrics   = () => apiV2.get('/system/metrics').then(r => r.data)
export const getSystemMetricsHistory = (minutes = 60) => apiV2.get(`/system/metrics/history?minutes=${minutes}`).then(r => r.data)

// Reports
export const getChannelReport   = (id: string, days = 7) => apiV2.get(`/reports/channels/${id}/summary?days=${days}`).then(r => r.data)
export const downloadReport     = (id: string, format: 'csv' | 'xlsx' | 'pdf', days = 7) => {
  const token = localStorage.getItem('access_token')
  return fetch(`/api/v1/reports/channels/${id}/export/${format}?days=${days}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

// Pinned channels
export const getPinned    = () => apiV2.get('/dashboard/pinned').then(r => r.data)
export const setPinned    = (channel_ids: string[]) => apiV2.post('/dashboard/pinned', { channel_ids }).then(r => r.data)
export const unpinChannel = (id: string) => apiV2.delete(`/dashboard/pinned/${id}`)

// Logs (v2.2)
export interface LogQueryParams {
  level?: string; logger?: string; search?: string
  since?: string; until?: string; limit?: number; offset?: number
}
export const queryLogs   = (params: LogQueryParams) => apiV2.get('/logs', { params }).then(r => r.data)
export const getLogStats = (hours = 24) => apiV2.get(`/logs/stats?hours=${hours}`).then(r => r.data)
export const purgeLogs   = (days: number) => apiV2.delete(`/logs/purge?days=${days}`)
export const emailLogEntry = (id: number, to_email: string) => apiV2.post(`/logs/${id}/email`, { to_email })
