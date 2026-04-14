import { Loader2, AlertTriangle } from 'lucide-react'
import type { ChannelStatus, ErrorSeverity } from '@/types'
import { STATUS_CONFIG, SEVERITY_CONFIG, cn } from '@/utils'

export function StatusBadge({status}:{status:ChannelStatus}){const cfg=STATUS_CONFIG[status];return<span className={cn('status-badge',`status-${status}`)}><span className={cn('w-1.5 h-1.5 rounded-full',cfg.dot)}/>{status}</span>}
export function SeverityBadge({severity}:{severity:ErrorSeverity}){const cfg=SEVERITY_CONFIG[severity];return<span className={cn('status-badge',cfg.bg,cfg.color)}>{severity}</span>}
export function Spinner({size=20,className}:{size?:number;className?:string}){return<Loader2 size={size} className={cn('animate-spin text-blue-500',className)}/>}
export function PageLoader(){return<div className="flex h-64 items-center justify-center"><Spinner size={32}/></div>}
export function ErrorDisplay({message='Something went wrong.'}:{message?:string}){return<div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"><AlertTriangle size={16} className="flex-shrink-0"/>{message}</div>}
export function EmptyState({message}:{message:string}){return<div className="py-12 text-center text-gray-400 text-sm">{message}</div>}
interface StatCardProps{label:string;value:string|number;sub?:string;color?:string;icon?:React.ReactNode}
export function StatCard({label,value,sub,color='text-gray-900',icon}:StatCardProps){return<div className="card p-5"><div className="flex items-start justify-between"><div><p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p><p className={cn('mt-1.5 text-3xl font-bold tabular-nums',color)}>{value}</p>{sub&&<p className="mt-1 text-xs text-gray-400">{sub}</p>}</div>{icon&&<div className="text-gray-400">{icon}</div>}</div></div>}
export function PageHeader({title,subtitle,actions}:{title:string;subtitle?:string;actions?:React.ReactNode}){return<div className="px-6 py-4 bg-white border-b border-gray-200 flex items-center justify-between flex-wrap gap-3"><div><h1 className="text-xl font-bold text-gray-900">{title}</h1>{subtitle&&<p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}</div>{actions&&<div className="flex items-center gap-2">{actions}</div>}</div>}
