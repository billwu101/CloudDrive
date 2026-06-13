import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { router } from './router'

const BASE = 'http://localhost:8000/api/v1'

const server = setupServer(
  http.get(`${BASE}/users/me`, () =>
    HttpResponse.json({ id: 'u1', email: 'a@test.com', username: 'alice', quota_bytes: 0, used_bytes: 0 }),
  ),
  http.get(`${BASE}/users/me/quota`, () =>
    HttpResponse.json({ quota_bytes: 1e9, used_bytes: 0, available_bytes: 1e9, used_percent: 0 }),
  ),
  http.get(`${BASE}/drive/items`, () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50, pages: 1 }),
  ),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
})
afterAll(() => server.close())

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const memRouter = createMemoryRouter(
    [
      ...router.routes,
    ],
    { initialEntries: [path] },
  )
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={memRouter} />
    </QueryClientProvider>,
  )
}

describe('RequireAuth', () => {
  it('redirects unauthenticated user from /drive to /login', () => {
    renderAt('/drive')
    expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
  })

  it('allows authenticated user to access /drive', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    renderAt('/drive')
    // drive page renders (empty state)
    expect(await screen.findByText(/this folder is empty/i)).toBeInTheDocument()
  })
})

describe('RedirectIfAuth', () => {
  it('redirects authenticated user from /login to /drive', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    renderAt('/login')
    expect(await screen.findByText(/this folder is empty/i)).toBeInTheDocument()
  })
})

describe('Public routes', () => {
  it('renders share-token page without login', () => {
    renderAt('/s/abc123')
    expect(screen.getByText(/shared file/i)).toBeInTheDocument()
  })

  it('renders 404 for unknown path', () => {
    renderAt('/nonexistent-page-xyz')
    expect(screen.getByRole('heading', { name: '404' })).toBeInTheDocument()
  })
})

describe('Folder route', () => {
  it('renders DrivePage with folderId param', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    renderAt('/drive/folder/folder-123')
    expect(await screen.findByText(/this folder is empty/i)).toBeInTheDocument()
  })
})
