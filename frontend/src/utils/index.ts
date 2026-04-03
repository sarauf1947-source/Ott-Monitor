import type { ChannelStatus, ErrorSeverity } from '@/types'

export const STATUS_CONFIG: Record<ChannelStatus, { label: string; color: string; dot: string; bg: string }> = {
  UP:      { label: 'UP',      color: 'text-green-700',  dot: 'bg-green-500',  bg: 'bg-green-50' },
  DOWN:    { label: 'DOWN',    color: 'text-red-700',    dot: 'bg-red-500',    bg: 'bg-red-50' },
  ERROR:   { label: 'ERROR',   color: 'text-amber-700',  dot: 'bg-amber-500',  bg: 'bg-amber-50' },
  WARNING: { label: 'WARNING', color: 'text-purple-700', dot: 'bg-purple-500', bg: 'bg-purple-50' },
  UNKNOWN: { label: 'UNKNOWN', color: 'text-gray-500',   dot: 'bg-gray-400',   bg: 'bg-gray-50' },
}

export const SEVERITY_CONFIG: Record<ErrorSeverity, { label: string; color: string; bg: string }> = {
  CRITICAL: { label: 'CRITICAL', color: 'text-red-700',    bg: 'bg-red-100' },
  MAJOR:    { label: 'MAJOR',    color: 'text-amber-700',  bg: 'bg-amber-100' },
  WARNING:  { label: 'WARNING',  color: 'text-purple-700', bg: 'bg-purple-100' },
  INFO:     { label: 'INFO',     color: 'text-blue-700',   bg: 'bg-blue-100' },
}

export function formatBitrate(kbps: number | null | undefined): string {
  if (!kbps) return '—'
  if (kbps >= 1000) return `${(kbps / 1000).toFixed(1)} Mbps`
  return `${kbps} kbps`
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const secs = Math.floor(diff / 1000)
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export function formatUptime(pct: number | null | undefined): string {
  if (pct == null) return '—'
  return `${pct.toFixed(1)}%`
}

export function formatMs(ms: number | null | undefined): string {
  if (!ms) return '—'
  return `${ms}ms`
}

export function formatAudioLevel(dbfs: number | null | undefined): string {
  if (dbfs == null) return '—'
  return `${dbfs.toFixed(1)} dBFS`
}

export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(' ')
}
