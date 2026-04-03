import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Radio, Bell, FileBarChart, Activity, Wifi
} from 'lucide-react'
import { useHealth } from '@/hooks/useApi'
import { cn } from '@/utils'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/channels',  icon: Radio,           label: 'Channels' },
  { to: '/alerts',    icon: Bell,            label: 'Alerts' },
  { to: '/reports',   icon: FileBarChart,    label: 'Reports' },
]

export default function Layout() {
  const { data: health } = useHealth()
  const isHealthy = health?.status === 'ok'

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 bg-slate-900 text-white flex flex-col">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-700">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
              <Activity size={16} className="text-white" />
            </div>
            <div>
              <div className="font-bold text-sm leading-none">OTT Monitor</div>
              <div className="text-slate-400 text-xs mt-0.5">NOC Dashboard</div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* API Health */}
        <div className="px-4 py-4 border-t border-slate-700">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Wifi size={12} />
            <span>API</span>
            <span className="ml-auto flex items-center gap-1.5">
              <span
                className={cn(
                  'w-2 h-2 rounded-full',
                  isHealthy ? 'bg-green-500' : 'bg-red-500'
                )}
              />
              {isHealthy ? 'Healthy' : health ? 'Degraded' : 'Connecting…'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
