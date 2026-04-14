// frontend/src/App.tsx  (v2.2)
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

import Layout            from '@/components/common/Layout'
import DashboardPage     from '@/pages/DashboardPage'
import ChannelsPage      from '@/pages/ChannelsPage'
import ChannelDetailPage from '@/pages/ChannelDetailPage'
import AlertsPage        from '@/pages/AlertsPage'
import ReportsPage       from '@/pages/ReportsPage'
import LoginPage         from '@/pages/LoginPage'
import UsersPage         from '@/pages/UsersPage'
import SettingsPage      from '@/pages/SettingsPage'
import InfrastructurePage from '@/pages/InfrastructurePage'
import LogsPage          from '@/pages/LogsPage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex h-screen items-center justify-center text-gray-400 text-sm">Loading...</div>
  if (!user)   return <Navigate to="/login" replace />
  return <>{children}</>
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, isAdmin } = useAuth()
  if (!user)    return <Navigate to="/login" replace />
  if (!isAdmin) return (
    <div className="flex h-screen items-center justify-center flex-col gap-3 text-gray-500">
      <p className="text-lg font-semibold">Access Denied</p>
      <p className="text-sm">Admin privileges required.</p>
    </div>
  )
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard"      element={<DashboardPage />} />
        <Route path="channels"       element={<ChannelsPage />} />
        <Route path="channels/:id"   element={<ChannelDetailPage />} />
        <Route path="alerts"         element={<AlertsPage />} />
        <Route path="reports"        element={<ReportsPage />} />
        <Route path="infrastructure" element={<InfrastructurePage />} />
        <Route path="logs"           element={<LogsPage />} />
        <Route path="settings"       element={<SettingsPage />} />
        <Route path="users"          element={<RequireAdmin><UsersPage /></RequireAdmin>} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
