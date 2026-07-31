import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

  it('does not repeat the folder name at the share root', async () => {
    server.use(
      http.post(`${BASE}/public/links/:token/session`, () =>
        HttpResponse.json(session({ item: FOLDER_ITEM })),
      ),
      http.get(`${BASE}/public/items/:id/children`, () =>
        HttpResponse.json({ items: [FILE_ITEM], total: 1, page: 1, page_size: 100, pages: 1 }),
      ),
    )
    renderPage()

    await screen.findByText('report.txt')
    // Once in the header — the root-level breadcrumb used to print it again.
    expect(screen.getAllByText('Photos')).toHaveLength(1)
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

// ── Editor links (proposal §33–§28.8) ─────────────────────────────────────────
//
// The guest page now uses My Drive's own components, so these drive it the way
// My Drive is driven: select a card, then act from the toolbar or the context
// menu — not from per-row buttons, which no longer exist.

const SUBFOLDER = { ...FILE_ITEM, id: 'sub-1', name: 'Docs', item_type: 'FOLDER' as const }

/** A DataTransfer stand-in — jsdom has no real one. */
function makeDataTransfer() {
  const store: Record<string, string> = {}
  return {
    types: [] as string[],
    effectAllowed: '',
    dropEffect: '',
    setData(type: string, value: string) {
      store[type] = value
      this.types = Object.keys(store)
    },
    getData(type: string) {
      return store[type] ?? ''
    },
    setDragImage() {},
  }
}

function editorSession(items: object[] = [FILE_ITEM]) {
  server.use(
    http.post(`${BASE}/public/links/:token/session`, () =>
      HttpResponse.json(session({ item: FOLDER_ITEM, permission: 'editor' })),
    ),
    http.get(`${BASE}/public/items/:id/children`, () =>
      HttpResponse.json({ items, total: items.length, page: 1, page_size: 100, pages: 1 }),
    ),
  )
}

/** The card for an item in the grid — clicking it selects, as in My Drive. */
function cardFor(name: string): HTMLElement {
  const el = screen.getByText(name).closest('[data-item-id]')
  if (!el) throw new Error(`no card for ${name}`)
  return el as HTMLElement
}

describe('ShareTokenPage editor links', () => {
  it('shows the drive toolbar and download on an editor folder link', async () => {
    editorSession()
    renderPage()

    expect(await screen.findByRole('button', { name: /Download folder/ })).toBeInTheDocument()
    expect(screen.getByText(/Can edit/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New folder' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Upload/ })).toBeInTheDocument()
  })

  it('never offers the owner-only affordances', async () => {
    editorSession()
    renderPage()

    await screen.findByText('report.txt')
    // proposal §28.8.2 — a guest has no account to hang a star on, and may not
    // re-share. Both come free with the reused components, so they are pinned.
    expect(screen.queryByRole('button', { name: 'Star' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Unstar' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Shared with other people')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Has an active public link')).not.toBeInTheDocument()
  })

  it('shows no edit controls on a downloader link', async () => {
    server.use(
      http.post(`${BASE}/public/links/:token/session`, () =>
        HttpResponse.json(session({ item: FOLDER_ITEM })),
      ),
      http.get(`${BASE}/public/items/:id/children`, () =>
        HttpResponse.json({ items: [FILE_ITEM], total: 1, page: 1, page_size: 100, pages: 1 }),
      ),
    )
    renderPage()

    await screen.findByText('report.txt')
    expect(screen.queryByRole('button', { name: 'New folder' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Upload/ })).not.toBeInTheDocument()
  })

  it('creates a folder through the shared dialog', async () => {
    let created: { parent_id: string; name: string } | null = null
    let children = [FILE_ITEM as object]
    server.use(
      http.post(`${BASE}/public/links/:token/session`, () =>
        HttpResponse.json(session({ item: FOLDER_ITEM, permission: 'editor' })),
      ),
      http.get(`${BASE}/public/items/:id/children`, () =>
        HttpResponse.json({
          items: children,
          total: children.length,
          page: 1,
          page_size: 100,
          pages: 1,
        }),
      ),
      http.post(`${BASE}/public/folders`, async ({ request }) => {
        created = (await request.json()) as { parent_id: string; name: string }
        children = [...children, SUBFOLDER]
        return HttpResponse.json(SUBFOLDER)
      }),
    )
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'New folder' }))
    await userEvent.type(screen.getByPlaceholderText('Folder name'), 'Docs')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(await screen.findByText('Docs')).toBeInTheDocument()
    expect(created).toEqual({ parent_id: FOLDER_ITEM.id, name: 'Docs' })
  })

  it('renames the item picked from the context menu', async () => {
    let renamed: { name: string } | null = null
    editorSession()
    server.use(
      http.patch(`${BASE}/public/items/:id/name`, async ({ params, request }) => {
        renamed = (await request.json()) as { name: string }
        expect(params['id']).toBe(FILE_ITEM.id)
        return HttpResponse.json({ ...FILE_ITEM, name: 'notes.txt' })
      }),
    )
    renderPage()

    fireEvent.contextMenu(cardFor(await screen.findByText('report.txt').then(() => 'report.txt')))
    await userEvent.click(await screen.findByRole('menuitem', { name: /Rename/ }))

    const field = screen.getByDisplayValue('report.txt')
    await userEvent.clear(field)
    await userEvent.type(field, 'notes.txt')
    await userEvent.click(screen.getByRole('button', { name: 'Rename' }))

    await waitFor(() => expect(renamed).toEqual({ name: 'notes.txt' }))
  })

  it('trashes the selection from the toolbar, after confirming', async () => {
    let trashed = false
    server.use(
      http.post(`${BASE}/public/links/:token/session`, () =>
        HttpResponse.json(session({ item: FOLDER_ITEM, permission: 'editor' })),
      ),
      http.get(`${BASE}/public/items/:id/children`, () =>
        HttpResponse.json(
          trashed
            ? { items: [], total: 0, page: 1, page_size: 100, pages: 0 }
            : { items: [FILE_ITEM], total: 1, page: 1, page_size: 100, pages: 1 },
        ),
      ),
      http.post(`${BASE}/public/items/:id/trash`, ({ params }) => {
        expect(params['id']).toBe(FILE_ITEM.id)
        trashed = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderPage()

    await screen.findByText('report.txt')
    await userEvent.click(cardFor('report.txt'))
    await userEvent.click(screen.getByRole('button', { name: /Trash \(1\)/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Move to trash' }))

    await waitFor(() => expect(trashed).toBe(true))
  })

  it('zips the selected items rather than the whole share', async () => {
    let body: { item_ids: string[] } | null = null
    editorSession([FILE_ITEM, SUBFOLDER])
    server.use(
      http.post(`${BASE}/public/archive`, async ({ request }) => {
        body = (await request.json()) as { item_ids: string[] }
        return HttpResponse.text('PK', {
          headers: { 'Content-Disposition': "attachment; filename*=UTF-8''picked.zip" },
        })
      }),
    )
    renderPage()

    await screen.findByText('report.txt')
    await userEvent.click(cardFor('report.txt'))
    await userEvent.click(screen.getByRole('button', { name: /Download \(1\)/ }))

    // proposal §28.8.3 — the selection travels in the body, not the whole root.
    await waitFor(() => expect(body).toEqual({ item_ids: [FILE_ITEM.id] }))
  })

  it('uploads a picked file into the current folder', async () => {
    let uploadedTo: string | null = null
    editorSession()
    server.use(
      http.post(`${BASE}/public/items/:id/upload`, async ({ params }) => {
        uploadedTo = String(params['id'])
        return HttpResponse.json({ ...FILE_ITEM, id: 'new-file', name: 'draft.txt' })
      }),
    )
    renderPage()

    await screen.findByRole('button', { name: /Upload/ })
    const file = new File(['draft body'], 'draft.txt', { type: 'text/plain' })
    // UploadMenu keeps its pickers hidden and aria-hidden, driven by the menu
    // items; the test drives the input the picker would have filled.
    const input = document.querySelector('input[type=file]') as HTMLInputElement
    await userEvent.upload(input, file)

    await waitFor(() => expect(uploadedTo).toBe(FOLDER_ITEM.id))
  })

  it('moves an item by dragging it onto a folder card', async () => {
    let moved: { parent_id: string } | null = null
    let movedId: string | null = null
    editorSession([SUBFOLDER, FILE_ITEM])
    server.use(
      http.patch(`${BASE}/public/items/:id/parent`, async ({ params, request }) => {
        movedId = String(params['id'])
        moved = (await request.json()) as { parent_id: string }
        return HttpResponse.json({ ...FILE_ITEM })
      }),
    )
    renderPage()

    await screen.findByText('report.txt')
    const dataTransfer = makeDataTransfer()
    fireEvent.dragStart(cardFor('report.txt'), { dataTransfer })
    fireEvent.dragOver(cardFor('Docs'), { dataTransfer })
    fireEvent.drop(cardFor('Docs'), { dataTransfer })

    await waitFor(() => expect(movedId).toBe(FILE_ITEM.id))
    expect(moved).toEqual({ parent_id: SUBFOLDER.id })
  })
})
