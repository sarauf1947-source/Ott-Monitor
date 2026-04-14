import type { ChannelStatus, ErrorSeverity } from '@/types'

export const STATUS_CONFIG: Record<ChannelStatus,{label:string;color:string;dot:string;bg:string}> = {
  UP:      {label:'UP',     color:'text-green-700', dot:'bg-green-500', bg:'bg-green-50'},
  DOWN:    {label:'DOWN',   color:'text-red-700',   dot:'bg-red-500',   bg:'bg-red-50'},
  ERROR:   {label:'ERROR',  color:'text-amber-700', dot:'bg-amber-500', bg:'bg-amber-50'},
  WARNING: {label:'WARNING',color:'text-purple-700',dot:'bg-purple-500',bg:'bg-purple-50'},
  UNKNOWN: {label:'UNKNOWN',color:'text-gray-500',  dot:'bg-gray-400',  bg:'bg-gray-50'},
}
export const SEVERITY_CONFIG: Record<ErrorSeverity,{label:string;color:string;bg:string}> = {
  CRITICAL:{label:'CRITICAL',color:'text-red-700',   bg:'bg-red-100'},
  MAJOR:   {label:'MAJOR',   color:'text-amber-700', bg:'bg-amber-100'},
  WARNING: {label:'WARNING', color:'text-purple-700',bg:'bg-purple-100'},
  INFO:    {label:'INFO',    color:'text-blue-700',  bg:'bg-blue-100'},
}
export const formatBitrate=(kbps:number|null|undefined):string=>{if(!kbps)return'-';return kbps>=1000?`${(kbps/1000).toFixed(1)} Mbps`:`${kbps} kbps`}
export const formatRelativeTime=(iso:string|null|undefined):string=>{if(!iso)return '-';const d=Date.now()-new Date(iso).getTime(),s=Math.floor(d/1000);if(s<60)return`${s}s ago`;const m=Math.floor(s/60);if(m<60)return`${m}m ago`;const h=Math.floor(m/60);if(h<24)return`${h}h ago`;return`${Math.floor(h/24)}d ago`}
export const formatDateTime=(iso:string|null|undefined):string=>iso?new Date(iso).toLocaleString():'-'
export const formatMs=(ms:number|null|undefined):string=>ms?`${ms}ms`:'-'
export const formatAudioLevel=(dbfs:number|null|undefined):string=>dbfs!=null?`${dbfs.toFixed(1)} dBFS`:'-'
export const cn=(...c:(string|undefined|false|null)[]):string=>c.filter(Boolean).join(' ')
