import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import type { SnapshotEntryResponse, SnapshotResponse } from '@/api/types'
import { useAuthStore } from '@/stores/authStore'

import { TimeMachinePage } from './TimeMachinePage'

const BASE = 'http://localhost:8000/api/v1'

const snapshot: SnapshotResponse = {
  id: 'snap-1',
  trigger: 'manual',
  label: 'manual',
  item_count: 2,
  total_bytes: 350,
  pinned: false,
  created_at: '2026-06-18T00:00:00Z',
}
const entries: SnapshotEntryResponse[] = [
  { item_id: 'i1', parent_item_id: null, name: 'docs', item_type: 'FOLDER', size_bytes: 0, checksum_sha256: null },
  { item_id: 'i2', parent_item_id: null, name: 'note.txt', item_type: 'FILE', size_bytes: 100, checksum_sha256: 'abc' },
]

let restored = false

const server = setupServer(
  http.get(`${BASE}/snapshots`, () => HttpResponse.json([snapshot])),
  http.get(`${BASE}/snapshots/:id/items`, () => HttpResponse.json(entries)),
  http.post(`${BASE}/snapshots/:id/restore`, () => {
    restored = true
    return HttpResponse.json({ pre_restore_snapshot_id: 'pre-1', restored: 2, trashed: 1 })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
  restored = false
  useAuthStore.setState({ accessToken: 'test-token', user: null })
})
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
})
afterAll(() => server.close())

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <TimeMachinePage />
    </QueryClientProvider>,
  )
}

describe('TimeMachinePage', () => {
  it('lists snapshots and browses a selected one', async () => {
    const user = userEvent.setup()
    renderPage()
    const row = await screen.findByText(/Manual · 2 items/i)
    await user.click(row)
    expect(await screen.findByText('docs')).toBeInTheDocument()
    expect(screen.getByText('note.txt')).toBeInTheDocument()
  })

  it('restores a whole snapshot after confirmation', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByText(/Manual · 2 items/i))
    await user.click(screen.getByRole('button', { name: /restore whole snapshot/i }))
    // confirm dialog
    await user.click(screen.getByRole('button', { name: /^restore$/i }))
    await waitFor(() => expect(restored).toBe(true))
    expect(await screen.findByText(/Restored 2 item/i)).toBeInTheDocument()
  })
})
