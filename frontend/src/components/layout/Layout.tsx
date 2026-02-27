import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useWebSocket } from '@/hooks/useWebSocket'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { connected, unreadCount } = useWebSocket()

  return (
    <div className="min-h-screen bg-background">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content area offset by sidebar width on desktop */}
      <div className="md:ml-60">
        <Header
          onMenuToggle={() => setSidebarOpen(prev => !prev)}
          wsConnected={connected}
          unreadCount={unreadCount}
        />
        <main className="p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
