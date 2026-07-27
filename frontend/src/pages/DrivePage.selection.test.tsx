import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import type { DriveItemResponse } from '@/api/types'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'

import { DrivePage } from './DrivePage'

const BASE = 'http://localhost:8000/api/v1'

function makeItem(id: string, name: string, type: 'FILE' | 'FOLDER'): DriveItemResponse {
  return {
    id,
    owner_id: 'u1',
    parent_id: null,
    item_type: type,
    name,
    mime_type: null,
    extension: null,
    size_bytes: 10,
    is_starred: false,
    is_deleted: false,
    deleted_at: null,
    created_by: 'u1',
    updated_by: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    is_shared_with_users: false,
    has_active_public_link: false,
  }
}

const ROOT_ITEMS = [makeItem('folder-1', 'sub', 'FOLDER'), makeItem('file-1', 'a.txt', 'FILE')]
const INNER_ITEMS = [makeItem('file-2', 'b.txt', 'FILE')]

const server = setupServer(
  http.get(`${BASE}/drive/items`, ({ request }) => {
    const parent = new URL(request.url).searchParams.get('parent_id')
    const items = parent ? INNER_ITEMS : ROOT_ITEMS
    return HttpResponse.json({ items, total: items.length, page: 1, page_size: 50, pages: 1 })
  }),
  http.get(`${BASE}/drive/items/:id/ancestors`, () => HttpResponse.json([])),
  http.get(`${BASE}/drive/items/:id`, ({ params }) =>
    HttpResponse.json(makeItem(String(params['id']), 'sub', 'FOLDER')),
  ),
  http.get(`${BASE}/assistant/skills`, () => HttpResponse.json([])),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
beforeEach(() => {
  useAuthStore.setState({ accessToken: 'tok' })
  useUIStore.getState().clearSelection()
})
afterEach(() => {
  server.resetHandlers()
  cleanup()
})
afterAll(() => server.close())

function renderDrive() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/drive']}>
        <Routes>
          <Route path="/drive" element={<DrivePage />} />
          <Route path="/drive/folder/:folderId" element={<DrivePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('DrivePage selection lifecycle', () => {
  it('drops the selection when you move into another folder', async () => {
    // Regression: the selection outlived the folder it belonged to. Because a
    // double-click both selects and navigates, entering a folder left that
    // folder selected — and the toolbar then offered to trash an item that
    // wasn't even on screen.
    renderDrive()
    await screen.findByText('a.txt')

    await userEvent.click(screen.getByLabelText('Select a.txt'))
    expect(screen.getByRole('button', { name: /Trash \(1\)/ })).toBeInTheDocument()

    await userEvent.dblClick(screen.getByText('sub'))

    await screen.findByText('b.txt')
    expect(screen.queryByRole('button', { name: /Trash/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Download/ })).not.toBeInTheDocument()
    // Not merely hidden — the ids are gone, so nothing stale can resurface
    // when you navigate back.
    await waitFor(() => expect(useUIStore.getState().selectedItemIds.size).toBe(0))
  })

  it('counts only what the current folder actually shows', async () => {
    // Even if a stale id survives in the store, it must not be actionable.
    useUIStore.getState().selectAll(['file-1', 'ghost-id'])
    renderDrive()
    await screen.findByText('a.txt')

    await userEvent.click(screen.getByLabelText('Select a.txt'))
    expect(screen.getByRole('button', { name: /Trash \(1\)/ })).toBeInTheDocument()
  })
})
