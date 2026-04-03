import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/common/Layout'
import DashboardPage from '@/pages/DashboardPage'
import ChannelsPage from '@/pages/ChannelsPage'
import ChannelDetailPage from '@/pages/ChannelDetailPage'
import AlertsPage from '@/pages/AlertsPage'
import ReportsPage from '@/pages/ReportsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="channels" element={<ChannelsPage />} />
        <Route path="channels/:id" element={<ChannelDetailPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="reports" element={<ReportsPage />} />
      </Route>
    </Routes>
  )
}
