import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { ShareDialog } from './ShareDialog'

const BASE = 'http://localhost:8000/api/v1'

const server = setupServer(
  http.post(`${BASE}/share/items/:id`, async ({ request }) => {
    const body = await request.json() as { target_email: string; permission: string }
    if (body.target_email === 'notfound@test.com') {
      return HttpResponse.json({ code: 'NOT_FOUND', message: 'User not found' }, { status: 404 })
    }
    return HttpResponse.json({
      id: 'sh1', item_id: 'item-1', owner_id: 'u1',
      target_user_id: 'u2', permission: body.permission,
      created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z',
    })
  }),
  http.post(`${BASE}/share/items/:id/links`, () =>
    HttpResponse.json({
      id: 'lnk1', item_id: 'item-1', token: 'abc-token',
      permission: 'viewer', expires_at: null, is_active: true,
      created_by: 'u1', created_at: '2024-01-01T00:00:00Z',
    }),
  ),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: 'tok' })
})
afterAll(() => server.close())

function renderDialog(open = true, onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ShareDialog open={open} itemId="item-1" itemName="My File.txt" onClose={onClose} />
    </QueryClientProvider>,
  )
}

describe('ShareDialog', () => {
  it('renders nothing when closed', () => {
    const { container } = renderDialog(false)
    expect(container).toBeEmptyDOMElement()
  })

  it('does not call share API when email is empty', async () => {
    renderDialog()
    // Do not type anything — email is empty
    await userEvent.click(screen.getByRole('button', { name: /^share$/i }))
    // API should NOT have been called (no success state appears)
    await new Promise((r) => setTimeout(r, 200))
    expect(screen.queryByText(/shared successfully/i)).not.toBeInTheDocument()
  })

  it('shares successfully with valid email', async () => {
    renderDialog()
    await userEvent.type(screen.getByLabelText(/email to share with/i), 'user@test.com')
    await userEvent.click(screen.getByRole('button', { name: /^share$/i }))
    await waitFor(() => expect(screen.getByText(/shared successfully/i)).toBeInTheDocument())
  })

  it('shows error from API', async () => {
    renderDialog()
    await userEvent.type(screen.getByLabelText(/email to share with/i), 'notfound@test.com')
    await userEvent.click(screen.getByRole('button', { name: /^share$/i }))
    await waitFor(() => expect(screen.getByText(/user not found/i)).toBeInTheDocument())
  })

  it('switches to link tab and creates link', async () => {
    renderDialog()
    await userEvent.click(screen.getByRole('button', { name: /link/i }))
    await userEvent.click(screen.getByRole('button', { name: /create link/i }))
    await waitFor(() => expect(screen.getByText(/copy link/i)).toBeInTheDocument())
  })

  it('changes permission via select', async () => {
    renderDialog()
    const select = screen.getByRole('combobox', { name: /permission level/i })
    await userEvent.selectOptions(select, 'editor')
    expect((select as HTMLSelectElement).value).toBe('editor')
  })
})
