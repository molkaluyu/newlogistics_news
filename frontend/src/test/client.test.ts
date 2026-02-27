import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setApiKey, clearApiKey, ApiError, api } from '@/api/client'

describe('setApiKey / clearApiKey', () => {
  beforeEach(() => localStorage.clear())

  it('stores the key in localStorage', () => {
    setApiKey('lnc_test123')
    expect(localStorage.getItem('lnc_api_key')).toBe('lnc_test123')
  })

  it('clearApiKey removes the key', () => {
    setApiKey('lnc_test123')
    clearApiKey()
    expect(localStorage.getItem('lnc_api_key')).toBeNull()
  })
})

describe('ApiError', () => {
  it('has correct name and status', () => {
    const err = new ApiError(404, 'Not found')
    expect(err.name).toBe('ApiError')
    expect(err.status).toBe(404)
    expect(err.message).toBe('Not found')
  })

  it('is an instance of Error', () => {
    const err = new ApiError(500, 'Server error')
    expect(err).toBeInstanceOf(Error)
  })
})

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GET sends correct request and parses JSON', async () => {
    const mockData = { id: 1, name: 'test' }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    const result = await api.get<typeof mockData>('/test')
    expect(result).toEqual(mockData)
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/test',
      expect.objectContaining({
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    )
  })

  it('includes X-API-Key header when key is set', async () => {
    setApiKey('lnc_mykey')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await api.get('/test')
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/test',
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-API-Key': 'lnc_mykey' }),
      }),
    )
  })

  it('does not include X-API-Key when no key is set', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    )

    await api.get('/test')
    const call = vi.mocked(fetch).mock.calls[0]
    const headers = call[1]?.headers as Record<string, string>
    expect(headers['X-API-Key']).toBeUndefined()
  })

  it('throws ApiError on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 }),
    )

    await expect(api.get('/missing')).rejects.toThrow(ApiError)
    await expect(api.get('/missing')).rejects.toMatchObject({ status: 404 })
  })

  it('handles 204 No Content', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 204 }),
    )

    const result = await api.del('/items/1')
    expect(result).toBeUndefined()
  })

  it('POST sends body as JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 1 }), { status: 201 }),
    )

    await api.post('/items', { name: 'test' })
    const call = vi.mocked(fetch).mock.calls[0]
    expect(call[1]?.method).toBe('POST')
    expect(call[1]?.body).toBe(JSON.stringify({ name: 'test' }))
  })

  it('PUT sends body as JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 1 }), { status: 200 }),
    )

    await api.put('/items/1', { name: 'updated' })
    const call = vi.mocked(fetch).mock.calls[0]
    expect(call[1]?.method).toBe('PUT')
    expect(call[1]?.body).toBe(JSON.stringify({ name: 'updated' }))
  })

  it('DEL sends DELETE method', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 204 }),
    )

    await api.del('/items/1')
    const call = vi.mocked(fetch).mock.calls[0]
    expect(call[1]?.method).toBe('DELETE')
  })
})
