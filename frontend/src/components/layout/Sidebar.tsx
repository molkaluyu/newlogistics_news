import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Newspaper,
  Search,
  BarChart3,
  Database,
  Bell,
  Settings,
  Ship,
  X,
} from 'lucide-react'

const navItems = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { label: 'News Feed', icon: Newspaper, path: '/feed' },
  { label: 'Search', icon: Search, path: '/search' },
  { label: 'Analytics', icon: BarChart3, path: '/analytics' },
  { label: 'Sources', icon: Database, path: '/sources' },
  { label: 'Subscriptions', icon: Bell, path: '/subscriptions' },
  { label: 'Settings', icon: Settings, path: '/settings' },
] as const

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { pathname } = useLocation()

  const isActive = (path: string) => {
    if (path === '/') return pathname === '/'
    return pathname.startsWith(path)
  }

  const sidebarContent = (
    <div className="flex h-full flex-col bg-sidebar-bg border-r border-border">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2.5 px-5 border-b border-border">
        <Ship className="h-6 w-6 text-primary shrink-0" />
        <span className="text-lg font-bold text-foreground">Logistics News</span>
        {/* Close button for mobile */}
        <button
          onClick={onClose}
          className="ml-auto rounded-md p-1 text-muted-foreground hover:text-foreground md:hidden"
          aria-label="Close sidebar"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map(({ label, icon: Icon, path }) => (
          <Link
            key={path}
            to={path}
            onClick={onClose}
            className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive(path)
                ? 'bg-primary text-primary-foreground'
                : 'text-sidebar-foreground hover:bg-accent hover:text-accent-foreground'
            }`}
          >
            <Icon className="h-5 w-5 shrink-0" />
            {label}
          </Link>
        ))}
      </nav>
    </div>
  )

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:fixed md:inset-y-0 md:left-0 md:z-30 md:flex md:w-60">
        {sidebarContent}
      </aside>

      {/* Mobile overlay */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50 md:hidden"
            onClick={onClose}
            aria-hidden="true"
          />
          <aside className="fixed inset-y-0 left-0 z-50 w-60 md:hidden">
            {sidebarContent}
          </aside>
        </>
      )}
    </>
  )
}
