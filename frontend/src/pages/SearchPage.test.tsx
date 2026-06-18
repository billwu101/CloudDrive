import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { SearchPage } from './SearchPage'

const BASE = 'http://localhost:8000/api/v1'

const file = (name: string) => ({
  id: `id-${name}`,
  owner_id: 'u1',
  parent_id: null,
  item_type: 'FILE',
  name,
  mime_type: 'application/pdf',
  extension: 'pdf',
  size_bytes: 1000,
  is_starred: false,
  is_deleted: false,
  deleted_at: null,
  created_by: 'u1',
  updated_by: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
})

const server = setupServer(
  http.get(`${BASE}/search`, () =>
    HttpResponse.json({
      items: [file('keyword_hit.pdf')],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    }),
  ),
  http.get(`${BASE}/search/semantic`, () =>
    HttpResponse.json([
      { item: file('semantic_hit.pdf'), score: 0.92, snippet: 'a relevant passage about budgets' },
    ]),
  ),
  http.post(`${BASE}/search/embeddings/backfill`, () =>
    HttpResponse.json({ indexed: 5, remaining: 0 }),
  ),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => useAuthStore.setState({ accessToken: 'test-token', user: null }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
})
afterAll(() => server.close())

function renderPage(query = 'budget') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/search?q=${query}`]}>
        <SearchPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SearchPage', () => {
  it('shows keyword results by default', async () => {
    renderPage()
    expect(await screen.findByText('keyword_hit.pdf')).toBeInTheDocument()
  })

  it('switches to semantic mode and shows relevance-ranked results', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('keyword_hit.pdf')

    await user.click(screen.getByRole('button', { name: /semantic/i }))

    expect(await screen.findByText('semantic_hit.pdf')).toBeInTheDocument()
    expect(screen.getByText(/sorted by relevance/i)).toBeInTheDocument()
    expect(screen.getByText(/92% match/i)).toBeInTheDocument() // relevance score
    expect(screen.getByText(/relevant passage/i)).toBeInTheDocument() // snippet
  })

  it('backfills embeddings for older files', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: /semantic/i }))
    await screen.findByText('semantic_hit.pdf')

    await user.click(screen.getByRole('button', { name: /index older files/i }))

    expect(await screen.findByText(/indexed 5 file/i)).toBeInTheDocument()
  })

  it('shows a guidance message when semantic search is disabled (503)', async () => {
    server.use(
      http.get(`${BASE}/search/semantic`, () =>
        HttpResponse.json({ detail: 'Semantic search is not enabled' }, { status: 503 }),
      ),
    )
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('keyword_hit.pdf')

    await user.click(screen.getByRole('button', { name: /semantic/i }))

    expect(await screen.findByText(/isn't enabled on this server/i)).toBeInTheDocument()
  })
})
