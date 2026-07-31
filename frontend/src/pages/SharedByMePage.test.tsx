import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { SharedByMePage } from './SharedByMePage'

const BASE = 'http://localhost:8000/api/v1'

const ITEM = {
  id: 'item-1',
  owner_id: 'u1',
  parent_id: null,
  item_type: 'FOLDER' as const,
  name: 'Deck',
  mime_type: null,
  extension: null,
  size_bytes: 0,
  is_starred: false,
  is_deleted: false,
  deleted_at: null,
  created_by: 'u1',
  updated_by: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  is_shared_with_users: true,
  has_active_public_link: true,
}

const ENTRY = {
  item: ITEM,
  user_shares: [
    {
      target_user_id: 'u2',
      email: 'bob@test.com',
      username: 'bob',
      permission: 'viewer',
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      target_user_id: 'u3',
      email: 'carol@test.com',
      username: 'carol',
      permission: 'downloader',
      created_at: '2024-01-01T00:00:00Z',
    },
  ],
  links: [
    {
      link_id: 'lnk-1',
      permission: 'viewer',
      has_password: true,
      expires_at: null,
      is_active: true,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      link_id: 'lnk-2',
      permission: 'viewer',
      has_password: false,
      expires_at: '2024-02-01T00:00:00Z',
      is_active: false,
      created_at: '2024-01-01T00:00:00Z',
    },
  ],
}

function pageOf(items: unknown[]) {
  return { items, total: items.length, page: 1, page_size: 20, pages: 1 }
}

const server = setupServer(
  http.get(`${BASE}/share/shared-by-me`, () => HttpResponse.json(pageOf([ENTRY]))),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterEach(() => {
  server.resetHandlers()
  cleanup()
})
afterAll(() => server.close())

function renderPage() {
  useAuthStore.setState({ accessToken: 'test-token' })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <SharedByMePage />
    </QueryClientProvider>,
  )
}

describe('SharedByMePage', () => {
  it('shows one row per item, however many shares it has', async () => {
    renderPage()

    expect(await screen.findByText('Deck')).toBeInTheDocument()
    expect(screen.getAllByText('Deck')).toHaveLength(1)
    // Collapsed: the individual recipients are not on screen yet.
    expect(screen.queryByText('bob@test.com')).not.toBeInTheDocument()
    expect(screen.getByText(/Shared with 2 people/)).toBeInTheDocument()
    expect(screen.getByText(/1 active public link/)).toBeInTheDocument()
  })

  it('reveals every recipient and link when expanded', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { expanded: false }))

    expect(screen.getByText('bob@test.com')).toBeInTheDocument()
    expect(screen.getByText('carol@test.com')).toBeInTheDocument()
    expect(screen.getByText(/password/)).toBeInTheDocument()
    // A dead link stays listed so the owner knows it existed.
    expect(screen.getByText(/Public link · expires .* · inactive/)).toBeInTheDocument()
  })

  it('offers a single Remove on every share, links included', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { expanded: false }))

    // Two recipients + two links = four Removes, and no Disable anywhere:
    // removing a link is the revocation, not a second step after it.
    expect(screen.getAllByRole('button', { name: 'Remove' })).toHaveLength(4)
    expect(screen.queryByRole('button', { name: 'Disable' })).not.toBeInTheDocument()
  })

  it('removes a single recipient in place', async () => {
    let removed: string | null = null
    server.use(
      http.delete(`${BASE}/share/items/:itemId/users/:userId`, ({ params }) => {
        removed = String(params['userId'])
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { expanded: false }))
    await userEvent.click(screen.getAllByRole('button', { name: 'Remove' })[0]!)

    await waitFor(() => expect(removed).toBe('u2'))
  })

  it('removes a live link outright', async () => {
    let removed: string | null = null
    server.use(
      http.delete(`${BASE}/share/links/:linkId/record`, ({ params }) => {
        removed = String(params['linkId'])
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { expanded: false }))
    // Third Remove: after the two recipients comes the active link.
    const buttons = screen.getAllByRole('button', { name: 'Remove' })
    await userEvent.click(buttons[2]!)

    await waitFor(() => expect(removed).toBe('lnk-1'))
  })

  it('copies a link URL the owner can no longer see anywhere else', async () => {
    let asked: string | null = null
    const written: string[] = []
    Object.assign(navigator, {
      clipboard: {
        writeText: (t: string) => {
          written.push(t)
          return Promise.resolve()
        },
      },
    })
    server.use(
      http.get(`${BASE}/share/links/:linkId/token`, ({ params }) => {
        asked = String(params['linkId'])
        return HttpResponse.json({ token: 'tok-recovered' })
      }),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { expanded: false }))
    await userEvent.click(screen.getAllByRole('button', { name: /Copy link/ })[0]!)

    // Fetched on click — the listing itself never carries the plaintext.
    await waitFor(() => expect(asked).toBe('lnk-1'))
    await waitFor(() => expect(written[0]).toContain('/s/tok-recovered'))
  })

  it('says so when a link predates the recoverable address', async () => {
    server.use(
      http.get(`${BASE}/share/links/:linkId/token`, () =>
        HttpResponse.json({ code: 'NOT_FOUND', message: 'gone' }, { status: 404 }),
      ),
    )
    renderPage()
    await userEvent.click(await screen.findByRole('button', { expanded: false }))
    await userEvent.click(screen.getAllByRole('button', { name: /Copy link/ })[0]!)

    // A fact about the link, not a transient error — so it replaces the button.
    expect(await screen.findByText('Address unavailable')).toBeInTheDocument()
  })

  it('offers no way to revoke everything at once', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { expanded: false }))

    // Revoking is irreversible; §29.5 decision 3 keeps it strictly per-record.
    expect(screen.queryByRole('button', { name: /revoke all/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /remove all/i })).not.toBeInTheDocument()
  })

  it('shows an empty state when nothing has been shared', async () => {
    server.use(http.get(`${BASE}/share/shared-by-me`, () => HttpResponse.json(pageOf([]))))
    renderPage()

    expect(await screen.findByText(/haven't shared anything yet/)).toBeInTheDocument()
  })
})
