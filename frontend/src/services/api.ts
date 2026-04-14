import axios from 'axios'
import type { AlertListResponse, Channel, ChannelListResponse, ChannelStatusSummary, DashboardSummary, HealthResponse, MetricListResponse, MetricSummary, StreamErrorListResponse } from '@/types'

const api = axios.create({ baseURL: '/api/v1', headers: {'Content-Type':'application/json'}, timeout: 15_000 })
api.interceptors.request.use(cfg=>{const t=localStorage.getItem('access_token');if(t)cfg.headers.Authorization=`Bearer ${t}`;return cfg})
api.interceptors.response.use(r=>r,err=>{if(err.response?.status===401){localStorage.removeItem('access_token');window.location.href='/login'}return Promise.reject(err)})

export const fetchChannels=(params?:Record<string,unknown>)=>api.get<ChannelListResponse>('/channels',{params}).then(r=>r.data)
export const fetchChannel=(id:string)=>api.get<Channel>(`/channels/${id}`).then(r=>r.data)
export const createChannel=(payload:Partial<Channel>)=>api.post<Channel>('/channels',payload).then(r=>r.data)
export const updateChannel=(id:string,payload:Partial<Channel>)=>api.patch<Channel>(`/channels/${id}`,payload).then(r=>r.data)
export const deleteChannel=(id:string)=>api.delete(`/channels/${id}`)
export const fetchChannelMetrics=(id:string,hours=24)=>api.get<MetricListResponse>(`/channels/${id}/metrics`,{params:{hours,limit:300}}).then(r=>r.data)
export const fetchMetricSummary=(id:string,hours=24)=>api.get<MetricSummary>(`/channels/${id}/metrics/summary`,{params:{hours}}).then(r=>r.data)
export const fetchChannelErrors=(id:string,hours=24)=>api.get<StreamErrorListResponse>(`/channels/${id}/errors`,{params:{hours,limit:100}}).then(r=>r.data)
export const fetchDashboardSummary=()=>api.get<DashboardSummary>('/dashboard/summary').then(r=>r.data)
export const fetchDashboardChannels=()=>api.get<ChannelStatusSummary[]>('/dashboard/channels').then(r=>r.data)
export const fetchAlerts=(params?:Record<string,unknown>)=>api.get<AlertListResponse>('/alerts',{params}).then(r=>r.data)
export const acknowledgeAlert=(id:string,acknowledgedBy:string)=>api.patch(`/alerts/${id}/acknowledge`,{acknowledged_by:acknowledgedBy}).then(r=>r.data)
export const resolveAlert=(id:string)=>api.patch(`/alerts/${id}/resolve`).then(r=>r.data)
export const fetchHealth=()=>api.get<HealthResponse>('/health').then(r=>r.data)
export const generateReport=(payload:unknown)=>api.post('/reports/generate',payload).then(r=>r.data)
export const downloadCsvReport=async(payload:unknown)=>{const resp=await api.post('/reports/export/csv',payload,{responseType:'blob'});const url=URL.createObjectURL(resp.data);const a=document.createElement('a');a.href=url;a.download=`ott_report_${Date.now()}.csv`;a.click();URL.revokeObjectURL(url)}
