import { api } from './client'

export interface Source {
  source_id: string
  name: string
  type: string
  url: string
  language: string
  categories?: string[]
  regions?: string[]
  enabled: boolean
  priority: number
  last_fetched_at?: string
  health_status?: string
  fetch_interval_minutes?: number
}

export interface SourceHealth {
  source_id: string
  name: string
  enabled: boolean
  health_status: string
  last_fetched_at?: string
  fetch_count_24h: number
  success_rate_24h: number
  total_articles_24h: number
  avg_duration_ms: number
  alerts?: string[]
}

export interface FetchLog {
  id: number
  source_id: string
  started_at: string
  completed_at?: string
  status: string
  articles_found: number
  articles_new: number
  articles_dedup: number
  error_message?: string
  duration_ms: number
}

export const sourcesApi = {
  list: () => api.get<Source[]>('/sources'),
  health: () => api.get<SourceHealth[]>('/health/sources'),
  fetchLogs: (params: { source_id?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams()
    if (params.source_id) qs.set('source_id', params.source_id)
    if (params.limit) qs.set('limit', String(params.limit))
    return api.get<FetchLog[]>(`/fetch-logs?${qs}`)
  },
}
