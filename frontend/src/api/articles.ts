import { api } from './client'

export interface Article {
  id: string
  source_id: string
  source_name: string
  url: string
  title: string
  body_text?: string
  body_markdown?: string
  summary_en?: string
  summary_zh?: string
  language: string
  published_at?: string
  fetched_at?: string
  transport_modes?: string[]
  primary_topic?: string
  secondary_topics?: string[]
  content_type?: string
  regions?: string[]
  entities?: Record<string, string[]>
  sentiment?: string
  market_impact?: string
  urgency?: string
  key_metrics?: Array<{ type: string; value: string }>
  processing_status: string
  llm_processed?: boolean
  raw_metadata?: Record<string, unknown>
}

export interface ArticlesResponse {
  total: number
  page: number
  page_size: number
  pages: number
  articles: Article[]
}

export interface ArticleFilters {
  source_id?: string
  transport_mode?: string
  topic?: string
  language?: string
  sentiment?: string
  urgency?: string
  from_date?: string
  to_date?: string
  search?: string
  page?: number
  page_size?: number
}

function buildQuery(filters: ArticleFilters): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== '' && v !== null) params.set(k, String(v))
  })
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export const articlesApi = {
  list: (filters: ArticleFilters = {}) =>
    api.get<ArticlesResponse>(`/articles${buildQuery(filters)}`),

  get: (id: string) => api.get<Article>(`/articles/${id}`),

  related: (id: string, limit = 5) =>
    api.get<{ article_id: string; related: Article[] }>(
      `/articles/${id}/related?limit=${limit}`
    ),

  semanticSearch: (q: string, filters: Partial<ArticleFilters> = {}, limit = 10) => {
    const params = new URLSearchParams({ q, limit: String(limit) })
    if (filters.transport_mode) params.set('transport_mode', filters.transport_mode)
    if (filters.topic) params.set('topic', filters.topic)
    if (filters.language) params.set('language', filters.language)
    return api.get<{ query: string; results: (Article & { similarity: number })[] }>(
      `/articles/search/semantic?${params}`
    )
  },
}
