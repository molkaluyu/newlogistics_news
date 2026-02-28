import { useEffect, useRef, useState, useCallback } from 'react'
import type { Article } from '@/api/articles'

interface WSFilters {
  transport_mode?: string
  topic?: string
  region?: string
  language?: string
}

export function useWebSocket(filters?: WSFilters) {
  const [articles, setArticles] = useState<Article[]>([])
  const [connected, setConnected] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const connect = useCallback(() => {
    const params = new URLSearchParams()
    if (filters?.transport_mode) params.set('transport_mode', filters.transport_mode)
    if (filters?.topic) params.set('topic', filters.topic)
    if (filters?.region) params.set('region', filters.region)
    if (filters?.language) params.set('language', filters.language)
    const qs = params.toString()
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/articles${qs ? `?${qs}` : ''}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, 5000)
    }
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'new_article' && msg.data) {
          setArticles(prev => [msg.data, ...prev].slice(0, 50))
          setUnreadCount(prev => prev + 1)
        }
      } catch { /* ignore parse errors */ }
    }
  }, [filters?.transport_mode, filters?.topic, filters?.region, filters?.language])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const clearUnread = useCallback(() => setUnreadCount(0), [])

  return { articles, connected, unreadCount, clearUnread }
}
