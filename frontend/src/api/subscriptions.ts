import { api } from './client'

export interface Subscription {
  id: string
  name: string
  source_ids?: string[]
  transport_modes?: string[]
  topics?: string[]
  regions?: string[]
  urgency_min?: string
  languages?: string[]
  channel: string
  channel_config?: Record<string, string>
  frequency: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface SubscriptionInput {
  name: string
  channel: string
  frequency?: string
  source_ids?: string[]
  transport_modes?: string[]
  topics?: string[]
  regions?: string[]
  urgency_min?: string
  languages?: string[]
  channel_config?: Record<string, string>
  enabled?: boolean
}

export const subscriptionsApi = {
  list: () => api.get<Subscription[]>('/subscriptions'),
  get: (id: string) => api.get<Subscription>(`/subscriptions/${id}`),
  create: (data: SubscriptionInput) => api.post<Subscription>('/subscriptions', data),
  update: (id: string, data: Partial<SubscriptionInput>) => api.put<Subscription>(`/subscriptions/${id}`, data),
  del: (id: string) => api.del<void>(`/subscriptions/${id}`),
}
