import { api } from './client'

export interface ApiKeyInfo {
  id: string
  name: string
  role: string
  enabled: boolean
  created_at: string
  last_used_at?: string
}

export interface ApiKeyCreateResponse {
  id: string
  name: string
  role: string
  api_key: string
  message: string
}

export interface HealthInfo {
  status: string
  article_count: number
  source_count: number
  last_fetch_at?: string
}

export const adminApi = {
  health: () => api.get<HealthInfo>('/health'),
  createApiKey: (name: string, role = 'reader') =>
    api.post<ApiKeyCreateResponse>('/admin/api-keys', { name, role }),
  listApiKeys: () => api.get<ApiKeyInfo[]>('/admin/api-keys'),
  deleteApiKey: (id: string) => api.del<void>(`/admin/api-keys/${id}`),
}
