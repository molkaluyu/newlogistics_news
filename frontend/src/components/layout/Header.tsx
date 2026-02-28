import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Menu, Search, Sun, Moon, Bell } from 'lucide-react'

interface HeaderProps {
  onMenuToggle: () => void
  wsConnected: boolean
  unreadCount: number
}

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/feed': 'News Feed',
  '/search': 'Semantic Search',
  '/analytics': 'Analytics',
  '/sources': 'Data Sources',
  '/discovery': 'Source Discovery',
  '/subscriptions': 'Subscriptions',
  '/settings': 'Settings',
}

function getPageTitle(pathname: string): string {
  if (pathname.startsWith('/articles/')) return 'Article'
  return pageTitles[pathname] ?? 'Logistics News'
}

export default function Header({ onMenuToggle, wsConnected, unreadCount }: HeaderProps) {
  const { pathname } = useLocation()
  const title = getPageTitle(pathname)

  const [dark, setDark] = useState(() => {
    if (typeof window === 'undefined') return false
    const stored = localStorage.getItem('theme')
    if (stored) return stored === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [dark])

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-card px-4 md:px-6">
      {/* Mobile hamburger */}
      <button
        onClick={onMenuToggle}
        className="rounded-md p-2 text-muted-foreground hover:text-foreground md:hidden"
        aria-label="Toggle menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Page title */}
      <h1 className="text-lg font-semibold text-foreground">{title}</h1>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Search shortcut */}
      <Link
        to="/search"
        className="rounded-md p-2 text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Search"
      >
        <Search className="h-5 w-5" />
      </Link>

      {/* WebSocket connection indicator */}
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground" title={wsConnected ? 'Connected' : 'Disconnected'}>
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full ${
            wsConnected ? 'bg-positive' : 'bg-muted-foreground'
          }`}
        />
        <span className="hidden sm:inline">{wsConnected ? 'Live' : 'Offline'}</span>
      </div>

      {/* Notification badge */}
      <div className="relative">
        <Bell className="h-5 w-5 text-muted-foreground" />
        {unreadCount > 0 && (
          <span className="absolute -top-1.5 -right-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </div>

      {/* Dark mode toggle */}
      <button
        onClick={() => setDark(prev => !prev)}
        className="rounded-md p-2 text-muted-foreground hover:text-foreground transition-colors"
        aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
      </button>
    </header>
  )
}
