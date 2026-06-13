import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import React from 'react'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { useCreateFolder, useDriveItems, useMoveToTrash, useRenameItem, useSetStarred } from './useDrive'

const BASE = 'http://localhost:8000/api/v1'

const ITEMS = [
  {
    id: 'f1', owner_id: 'u1', parent_id: null, item_type: 'FOLDER', name: 'Docs',
    mime_type: null, extension: null, size_bytes: 0, is_starred: false, is_deleted: false,
    deleted_at: null, created_by: 'u1', updated_by: null, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'fi1', owner_id: 'u1', parent_id: null, item_type: 'FILE', name: 'note.txt',
    mime_type: 'text/plain', extension: 'txt', size_bytes: 100, is_starred: true, is_deleted: false,
    deleted_at: null, created_by: 'u1', updated_by: null, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z',
  },
]

const server = setupServer(
  http.get(`${BASE}/drive/items`, () =>
    HttpResponse.json({ items: ITEMS, total: 2, page: 1, page_size: 50, pages: 1 }),
  ),
  http.post(`${BASE}/drive/items/folders`, () =>
    HttpResponse.json({ ...ITEMS[0], id: 'new-folder', name: 'New Folder' }),
  ),
  http.patch(`${BASE}/drive/items/:id/rename`, () =>
    HttpResponse.json({ ...ITEMS[1], name: 'renamed.txt' }),
  ),
  http.post(`${BASE}/trash/items/:id`, () => HttpResponse.json({})),
  http.patch(`${BASE}/drive/items/:id/star`, () =>
    HttpResponse.json({ ...ITEMS[1], is_starred: false }),
  ),
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

describe('useDriveItems', () => {
  it('returns items from API', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    const { result } = renderHook(() => useDriveItems(), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.items).toHaveLength(2)
    expect(result.current.data?.items[0].name).toBe('Docs')
  })
})

describe('useCreateFolder', () => {
  it('fires mutation and resolves', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    const { result } = renderHook(() => useCreateFolder(), { wrapper: makeWrapper() })
    result.current.mutate('New Folder')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})

describe('useRenameItem', () => {
  it('fires rename mutation', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    const { result } = renderHook(() => useRenameItem(), { wrapper: makeWrapper() })
    result.current.mutate({ id: 'fi1', name: 'renamed.txt' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})

describe('useMoveToTrash', () => {
  it('fires trash mutation', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    const { result } = renderHook(() => useMoveToTrash(), { wrapper: makeWrapper() })
    result.current.mutate('fi1')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})

describe('useSetStarred', () => {
  it('fires star mutation', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    const { result } = renderHook(() => useSetStarred(), { wrapper: makeWrapper() })
    result.current.mutate({ id: 'fi1', starred: false })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })
})
