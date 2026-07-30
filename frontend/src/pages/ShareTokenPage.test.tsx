import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { ShareTokenPage } from './ShareTokenPage'

const BASE = 'http://localhost:8000/api/v1'

const FILE_ITEM = {
  id: 'item-1',
  name: 'report.txt',
  item_type: 'FILE' as const,
  mime_type: 'text/plain',
  size_bytes: 2048,
  extension: 'txt',
  preview_type: 'text' as const,
  updated_at: '2024-01-01T00:00:00Z',
}

const FOLDER_ITEM = { ...FILE_ITEM, id: 'folder-1', name: 'Photos', item_type: 'FOLDER' as const }

function session(overrides: Record<string, unknown> = {}) {
  return {
    access_token: 'share-cred',
    expires_in: 900,
    permission: 'downloader',
    item: FILE_ITEM,
    ...overrides,
  }
}

const server = setupServer(
  http.get(`${BASE}/public/items/:id/preview`, () =>
    HttpResponse.text('file body', { headers: { 'Content-Type': 'text/plain' } }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterEach(() => {
  server.resetHandlers()
  cleanup()
})
afterAll(() => server.close())

function renderPage(token = 'tok-abc') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/s/${token}`]}>
        <Routes>
          <Route path="/s/:shareToken" element={<ShareTokenPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ShareTokenPage', () => {
  it('opens a link with no password without asking for one', async () => {
    server.use(http.post(`${BASE}/public/links/:token/session`, () => HttpResponse.json(session())))
    renderPage()

    expect(await screen.findByText('report.txt')).toBeInTheDocument()
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
  })

  it('asks for a password only when the link has one', async () => {
    server.use(
      http.post(`${BASE}/public/links/:token/session`, async ({ request }) => {
        const body = (await request.json()) as { password: string | null }
        if (body.password === 'letmein') return HttpResponse.json(session())
        if (body.password === null) {
          return HttpResponse.json(
            { code: 'SHARE_LINK_PASSWORD_REQUIRED', message: 'Password required' },
            { status: 401 },
          )
        }
        return HttpResponse.json(
          { code: 'SHARE_LINK_INVALID', message: 'Link is invalid' },
          { status: 404 },
        )
      }),
    )
    renderPage()

    const field = await screen.findByLabelText('Password')
    // Nothing about the file may show before the password is accepted.
    expect(screen.queryByText('report.txt')).not.toBeInTheDocument()

    await userEvent.type(field, 'letmein')
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))

    expect(await screen.findByText('report.txt')).toBeInTheDocument()
  })

  it('shows the same wording for a wrong password as for a dead link', async () => {
    server.use(
      http.post(`${BASE}/public/links/:token/session`, async ({ request }) => {
        const body = (await request.json()) as { password: string | null }
        if (body.password === null) {
          return HttpResponse.json({ code: 'SHARE_LINK_PASSWORD_REQUIRED' }, { status: 401 })
        }
        return HttpResponse.json({ code: 'SHARE_LINK_INVALID' }, { status: 404 })
      }),
    )
    renderPage()

    await userEvent.type(await screen.findByLabelText('Password'), 'nope')
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('This link is invalid or no longer available.')
  })

  it('shows the generic message for an unknown token', async () => {
    server.use(
      http.post(`${BASE}/public/links/:token/session`, () =>
        HttpResponse.json({ code: 'SHARE_LINK_INVALID' }, { status: 404 }),
      ),
    )
    renderPage('garbage')

    expect(
      await screen.findByText('This link is invalid or no longer available.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Link unavailable')).toBeInTheDocument()
  })

  it('hides download controls on a viewer link', async () => {
    server.use(
      http.post(`${BASE}/public/links/:token/session`, () =>
        HttpResponse.json(session({ permission: 'viewer' })),
      ),
    )
    renderPage()

    await screen.findByText('report.txt')
    expect(screen.queryByRole('button', { name: 'Download' })).not.toBeInTheDocument()
    expect(screen.getByText(/View only/)).toBeInTheDocument()
  })

  it('offers a zip download for a downloader folder link', async () => {
    server.use(
      http.post(`${BASE}/public/links/:token/session`, () =>
        HttpResponse.json(session({ item: FOLDER_ITEM })),
      ),
      http.get(`${BASE}/public/items/:id/children`, () =>
        HttpResponse.json({ items: [FILE_ITEM], total: 1, page: 1, page_size: 100, pages: 1 }),
      ),
    )
    renderPage()

    expect(await screen.findByRole('button', { name: /Download folder/ })).toBeInTheDocument()
    expect(await screen.findByText('report.txt')).toBeInTheDocument()
  })

  it('sends the credential from the session on later requests', async () => {
    let seen: string | null = null
    server.use(
      http.post(`${BASE}/public/links/:token/session`, () =>
        HttpResponse.json(session({ item: FOLDER_ITEM })),
      ),
      http.get(`${BASE}/public/items/:id/children`, ({ request }) => {
        seen = request.headers.get('Authorization')
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100, pages: 0 })
      }),
    )
    renderPage()

    await waitFor(() => expect(seen).toBe('Bearer share-cred'))
  })

  it('never sends the password in the URL', async () => {
    let requestUrl = ''
    server.use(
      http.post(`${BASE}/public/links/:token/session`, async ({ request }) => {
        requestUrl = request.url
        const body = (await request.json()) as { password: string | null }
        if (body.password === null) {
          return HttpResponse.json({ code: 'SHARE_LINK_PASSWORD_REQUIRED' }, { status: 401 })
        }
        return HttpResponse.json(session())
      }),
    )
    renderPage()

    await userEvent.type(await screen.findByLabelText('Password'), 'hunter2')
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))

    await screen.findByText('report.txt')
    expect(requestUrl).not.toContain('hunter2')
  })
})
