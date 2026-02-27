import { api } from './client'

export interface TrendingTopic {
  topic: string
  count: number
  growth_rate?: number
}

export interface SentimentPoint {
  period: string
  positive: number
  negative: number
  neutral: number
  total: number
}

export interface Entity {
  name: string
  type: string
  count: number
}

export interface EntityGraphNode {
  id: string
  name: string
  type: string
  count: number
}

export interface EntityGraphLink {
  source: string
  target: string
  weight: number
}

export interface EntityGraph {
  nodes: EntityGraphNode[]
  links: EntityGraphLink[]
}

export const analyticsApi = {
  trending: (params: { time_window?: string; transport_mode?: string; region?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v) qs.set(k, String(v)) })
    return api.get<TrendingTopic[]>(`/analytics/trending?${qs}`)
  },

  sentimentTrend: (params: { granularity?: string; transport_mode?: string; topic?: string; region?: string; days?: number } = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v) qs.set(k, String(v)) })
    return api.get<SentimentPoint[]>(`/analytics/sentiment-trend?${qs}`)
  },

  entities: (params: { entity_type?: string; days?: number; limit?: number } = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v) qs.set(k, String(v)) })
    return api.get<Entity[]>(`/analytics/entities?${qs}`)
  },

  entityGraph: (params: { days?: number; min_cooccurrence?: number; limit?: number } = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v) qs.set(k, String(v)) })
    return api.get<EntityGraph>(`/analytics/entities/graph?${qs}`)
  },
}
