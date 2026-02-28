const BASE_URL = '/api/v1'

function getApiKey(): string | null {
  return localStorage.getItem('lnc_api_key')
}

export function setApiKey(key: string) {
  localStorage.setItem('lnc_api_key', key)
}

export function clearApiKey() {
  localStorage.removeItem('lnc_api_key')
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  }
  const key = getApiKey()
  if (key) headers['X-API-Key'] = key

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail || res.statusText)
  }
  // Handle 204 No Content
  if (res.status === 204) return undefined as T
  return res.json()
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
