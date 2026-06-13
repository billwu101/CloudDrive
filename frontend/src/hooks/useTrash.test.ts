import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import React from 'react'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { useEmptyTrash, usePermanentDelete, useRestoreItem, useTrashItems } from './useTrash'

const BASE = 'http://localhost:8000/api/v1'

const DELETED_ITEM = {
  id: 'd1', owner_id: 'u1', parent_id: null, item_type: 'FILE', name: 'old.txt',
  mime_type: 'text/plain', extension: 'txt', size_bytes: 100, is_starred: false,
  is_deleted: true, deleted_at: '2024-06-01T00:00:00Z',
  created_by: 'u1', updated_by: null, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-06-01T00:00:00Z',
}

const server = setupServer(
  http.get(`${BASE}/trash`, () =>
    HttpResponse.json({ items: [DELETED_ITEM], total: 1, page: 1, page_size: 50, pages: 1 }),
  ),
  http.post(`${BASE}/trash/items/:id/restore`, () =>
    HttpResponse.json({ ...DELETED_ITEM, is_deleted: false, deleted_at: null }),
  ),
  http.delete(`${BASE}/trash/items/:id`, () => new HttpResponse(null, { status: 204 })),
  http.delete(`${BASE}/trash`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  useAuthStore.setState({ accessToken: 'tok' })
})
afterAll(() => server.close())

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('useTrashItems', () => {
  it('returns deleted items', async () => {
    const { result } = renderHook(() => useTrashItems(), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.items).toHaveLength(1)
    expect(result.current.data?.items[0].name).toBe('old.txt')
  })
})

describe('useRestoreItem', () => {
  it('fires restore mutation', async () => {
    const { result } = renderHook(() => useRestoreItem(), { wrapper: makeWrapper() })
    result.current.mutate('d1')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})

describe('usePermanentDelete', () => {
  it('fires permanent delete mutation', async () => {
    const { result } = renderHook(() => usePermanentDelete(), { wrapper: makeWrapper() })
    result.current.mutate('d1')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})

describe('useEmptyTrash', () => {
  it('fires empty trash mutation', async () => {
    const { result } = renderHook(() => useEmptyTrash(), { wrapper: makeWrapper() })
    result.current.mutate()
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})
