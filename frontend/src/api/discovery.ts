import { api } from './client'

export interface SourceCandidate {
  id: string
  url: string
  name?: string
  feed_url?: string
  source_type: string
  language?: string
  categories?: string[]
  discovered_via?: string
  discovery_query?: string
  status: string
  quality_score?: number
  relevance_score?: number
  articles_fetched: number
  fetch_success?: boolean
  error_message?: string
  auto_approved: boolean
  sample_articles?: Array<{
    title: string
    url: string
    body_preview: string
    published_at?: string
  }>
  validation_details?: Record<string, unknown>
  created_at?: string
  validated_at?: string
}

export interface CandidatesResponse {
  total: number
  page: number
  page_size: number
  pages: number
  candidates: SourceCandidate[]
}

export interface DiscoveryStatus {
  running: boolean
  last_scan_at?: string
  last_validate_at?: string
  scan_in_progress: boolean
  validate_in_progress: boolean
  total_scans: number
  total_validations: number
  last_scan_result?: Record<string, unknown>
  last_validate_result?: Record<string, unknown>
  count_discovered: number
  count_validating: number
  count_validated: number
  count_approved: number
  count_rejected: number
}

export interface ProbeResult {
  url: string
  final_url?: string
  reachable: boolean
  name?: string
  feed_url?: string
  source_type?: string
  articles_fetched: number
  quality_score: number
  relevance_score: number
  combined_score: number
  sample_articles?: Array<{ title: string; url: string; body_preview: string }>
  fetch_error?: string
  error?: string
}

export interface CandidateFilters {
  status?: string
  language?: string
  min_quality?: number
  sort?: string
  page?: number
  page_size?: number
}

function buildQuery(filters: CandidateFilters): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== '' && v !== null) params.set(k, String(v))
  })
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export const discoveryApi = {
  status: () => api.get<DiscoveryStatus>('/discovery/status'),
  start: () => api.post<DiscoveryStatus>('/discovery/start'),
  stop: () => api.post<DiscoveryStatus>('/discovery/stop'),
  scan: () => api.post<{ candidates_found: number; candidates: unknown[] }>('/discovery/scan'),
  validate: (limit = 10) =>
    api.post<{ validated: number; auto_approved: number }>(`/discovery/validate?limit=${limit}`),
  candidates: (filters: CandidateFilters = {}) =>
    api.get<CandidatesResponse>(`/discovery/candidates${buildQuery(filters)}`),
  approve: (id: string) =>
    api.post<{ id: string; status: string; message: string }>(
      `/discovery/candidates/${id}/approve`
    ),
  reject: (id: string) =>
    api.post<{ id: string; status: string }>(`/discovery/candidates/${id}/reject`),
  probe: (url: string) => api.post<ProbeResult>('/discovery/probe', { url }),
}
