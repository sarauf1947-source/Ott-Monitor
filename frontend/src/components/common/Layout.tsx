// frontend/src/components/common/Layout.tsx  (v2.3)
// Change: toast duration now reads from localStorage key 'toast_duration'
// which is set by Settings > Notifications > "Toast duration" slider (1-10s).
// All other behaviour unchanged from v2.2.
import { useState, useEffect, useRef } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Radio, Bell, FileBarChart, Activity, Wifi,
  Server, Settings, Users, ChevronLeft, ChevronRight, LogOut, ScrollText,
} from 'lucide-react'
import { useHealth }  from '@/hooks/useApi'
import { useAuth }    from '@/context/AuthContext'
import { apiV2 }      from '@/services/apiV2'
import { cn }         from '@/utils'

const NAV_MAIN = [
  { to: '/dashboard',      icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/channels',       icon: Radio,           label: 'Channels'  },
  { to: '/alerts',         icon: Bell,            label: 'Alerts'    },
  { to: '/reports',        icon: FileBarChart,    label: 'Reports'   },
  { to: '/infrastructure', icon: Server,          label: 'Infrastructure' },
  { to: '/logs',           icon: ScrollText,      label: 'Logs'      },
]
const NAV_ADMIN = [
  { to: '/settings', icon: Settings, label: 'Settings' },
  { to: '/users',    icon: Users,    label: 'Users'    },
]

function beep(vol = 0.25) {
  try {
    const ctx  = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
    const osc  = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.frequency.value = 880; osc.type = 'sine'; gain.gain.value = vol
    osc.start(); osc.stop(ctx.currentTime + 0.15)
  } catch { /* ignore */ }
}

interface Toast { id: number; message: string; detail?: string; level: string; href?: string }
let _lastAlertId = ''
let _toastId     = 0

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none',
        checked ? 'bg-blue-500' : 'bg-slate-600'
      )}>
      <span className={cn(
        'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
        checked ? 'translate-x-4' : 'translate-x-1'
      )} />
    </button>
  )
}

export default function Layout() {
  const { data: health }           = useHealth()
  const { user, signOut, isAdmin } = useAuth()
  const navigate                   = useNavigate()
  const isHealthy                  = health?.status === 'ok'

  const [collapsed,  setCollapsed]  = useState(() => localStorage.getItem('sidebar_collapsed') === 'true')
  const [soundOn,    setSoundOn]    = useState(() => localStorage.getItem('alert_sound') !== 'false')
  const [notifOn,    setNotifOn]    = useState(() => localStorage.getItem('alert_notif') !== 'false')
  const [alertCount, setAlertCount] = useState(0)
  const [toasts,     setToasts]     = useState<Toast[]>([])
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => { localStorage.setItem('sidebar_collapsed', String(collapsed)) }, [collapsed])
  useEffect(() => { localStorage.setItem('alert_sound',        String(soundOn))  }, [soundOn])
  useEffect(() => { localStorage.setItem('alert_notif',        String(notifOn))  }, [notifOn])

  // Read toast duration from localStorage (set by Settings > Notifications)
  // Default 5 seconds if not configured.
  const getToastMs = () => {
    const v = parseInt(localStorage.getItem('toast_duration') ?? '5', 10)
    return (isNaN(v) ? 5 : Math.min(Math.max(v, 1), 10)) * 1000
  }

  const addToast = (message: string, level: string, detail?: string, href?: string) => {
    const id  = ++_toastId
    const dur = getToastMs()
    setToasts(prev => [{ id, message, detail, level, href }, ...prev.slice(0, 4)])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), dur)
  }

  useEffect(() => {
    const poll = async () => {
      try {
        const res      = await apiV2.get('/alerts?status=OPEN&limit=50')
        const items    = res.data?.items ?? []
        const critMaj  = items.filter((a: { severity: string }) =>
          a.severity === 'CRITICAL' || a.severity === 'MAJOR'
        )
        setAlertCount(critMaj.length)
        if (critMaj.length > 0) {
          const newest = critMaj[0]
          if (newest.id !== _lastAlertId) {
            _lastAlertId = newest.id
            if (notifOn) {
              addToast(
                `${newest.severity}: ${newest.channel_name ?? 'Unknown channel'}`,
                newest.severity,
                newest.message ?? newest.alert_type,
                `/alerts?highlight=${newest.id}`
              )
            }
            if (soundOn) beep(0.25)
          }
        }
      } catch { /* ignore */ }
    }
    poll()
    pollRef.current = setInterval(poll, 30_000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [soundOn, notifOn])

  const handleLogout = () => { signOut(); navigate('/login') }

  const toastColors: Record<string, string> = {
    CRITICAL: 'bg-red-600 text-white',
    MAJOR:    'bg-amber-500 text-white',
    WARNING:  'bg-purple-600 text-white',
    INFO:     'bg-blue-600 text-white',
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">

      {/* Toasts */}
      <div className="fixed top-4 right-4 z-50 space-y-2 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id}
            className={cn(
              'px-4 py-3 rounded-lg shadow-lg text-sm font-medium pointer-events-auto',
              'flex items-start gap-3 min-w-[320px] max-w-[420px]',
              toastColors[t.level] ?? 'bg-gray-800 text-white'
            )}>
            <Bell size={14} className="mt-0.5 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="font-semibold">{t.message}</div>
              {t.detail && <div className="text-xs opacity-90 mt-1 break-words">{t.detail}</div>}
            </div>
            {t.href && (
              <button
                onClick={() => navigate(t.href!)}
                className="text-xs font-semibold underline underline-offset-2 hover:opacity-80">
                View
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Sidebar */}
      <aside className={cn(
        'flex-shrink-0 bg-slate-900 text-white flex flex-col transition-all duration-200',
        collapsed ? 'w-16' : 'w-60'
      )}>
        {/* Logo */}
        <div className={cn('flex items-center border-b border-slate-700 h-16', collapsed ? 'justify-center' : 'gap-2.5 px-5')}>
          <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center flex-shrink-0">
            <Activity size={16} className="text-white" />
          </div>
          {!collapsed && (
            <div>
              <div className="font-bold text-sm leading-none">OTT Monitor</div>
              <div className="text-slate-400 text-xs mt-0.5">NOC v2.3</div>
            </div>
          )}
        </div>

        {/* Toggle button */}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="mx-auto my-2 w-7 h-7 rounded-md bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-400 hover:text-white"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
        </button>

        {/* Nav */}
        <nav className="flex-1 px-2 py-2 space-y-0.5 overflow-y-auto">
          {NAV_MAIN.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} title={collapsed ? label : undefined}
              className={({ isActive }) => cn(
                'flex items-center gap-3 px-2 py-2.5 rounded-lg text-sm font-medium transition-colors',
                collapsed && 'justify-center',
                isActive ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              )}>
              <Icon size={16} className="flex-shrink-0" />
              {!collapsed && label}
              {label === 'Alerts' && alertCount > 0 && !collapsed && (
                <span className="ml-auto bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
                  {alertCount}
                </span>
              )}
            </NavLink>
          ))}

          {isAdmin && (
            <>
              {!collapsed && (
                <div className="pt-3 pb-1 px-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Admin</p>
                </div>
              )}
              {NAV_ADMIN.map(({ to, icon: Icon, label }) => (
                <NavLink key={to} to={to} title={collapsed ? label : undefined}
                  className={({ isActive }) => cn(
                    'flex items-center gap-3 px-2 py-2.5 rounded-lg text-sm font-medium transition-colors',
                    collapsed && 'justify-center',
                    isActive ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  )}>
                  <Icon size={16} className="flex-shrink-0" />
                  {!collapsed && label}
                </NavLink>
              ))}
            </>
          )}
        </nav>

        {/* Notification toggles */}
        {!collapsed && (
          <div className="border-t border-slate-700 px-4 py-3 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Alert Popups</span>
              <Toggle checked={notifOn} onChange={setNotifOn} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Alert Sound</span>
              <Toggle checked={soundOn} onChange={setSoundOn} />
            </div>
          </div>
        )}

        {/* API health */}
        <div className={cn('border-t border-slate-700 py-3', collapsed ? 'px-2 flex justify-center' : 'px-4')}>
          {collapsed ? (
            <span className={cn('w-2.5 h-2.5 rounded-full', isHealthy ? 'bg-green-500' : 'bg-red-500')}
                  title={isHealthy ? 'API healthy' : 'API degraded'} />
          ) : (
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Wifi size={12} /><span>API</span>
              <span className="ml-auto flex items-center gap-1.5">
                <span className={cn('w-2 h-2 rounded-full', isHealthy ? 'bg-green-500' : 'bg-red-500')} />
                {isHealthy ? 'Healthy' : health ? 'Degraded' : 'Connecting...'}
              </span>
            </div>
          )}
        </div>

        {/* User + Logout */}
        <div className={cn('border-t border-slate-700 py-3 space-y-1', collapsed ? 'px-2' : 'px-3')}>
          {!collapsed && user && (
            <div className="flex items-center gap-2 px-2 py-1">
              <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
                {user.username[0].toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white truncate">{user.full_name || user.username}</p>
                <p className="text-xs text-slate-400 capitalize">{user.role}</p>
              </div>
            </div>
          )}
          <button onClick={handleLogout} title="Logout"
            className={cn(
              'flex items-center gap-2 w-full px-2 py-2 rounded-lg text-xs font-medium',
              'text-slate-400 hover:bg-red-900/40 hover:text-red-300 transition-colors',
              collapsed && 'justify-center'
            )}>
            <LogOut size={14} className="flex-shrink-0" />
            {!collapsed && 'Logout'}
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto"><Outlet /></main>
    </div>
  )
}
