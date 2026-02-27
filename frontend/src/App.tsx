import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/layout/Layout'
import DashboardPage from '@/pages/DashboardPage'
import FeedPage from '@/pages/FeedPage'
import SearchPage from '@/pages/SearchPage'
import ArticlePage from '@/pages/ArticlePage'
import AnalyticsPage from '@/pages/AnalyticsPage'
import SourcesPage from '@/pages/SourcesPage'
import SubscriptionsPage from '@/pages/SubscriptionsPage'
import SettingsPage from '@/pages/SettingsPage'
import DiscoveryPage from '@/pages/DiscoveryPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/feed" element={<FeedPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/articles/:id" element={<ArticlePage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/discovery" element={<DiscoveryPage />} />
        <Route path="/subscriptions" element={<SubscriptionsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
