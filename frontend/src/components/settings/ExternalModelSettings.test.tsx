import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { ExternalModelSettings } from './ExternalModelSettings'

const BASE = 'http://localhost:8000/api/v1'
const PATH = `${BASE}/users/me/external-credentials`

let creds: unknown[] = []
let lastPut: unknown = null
let deleted = false

const server = setupServer(
  http.get(PATH, () => HttpResponse.json(creds)),
  http.put(PATH, async ({ request }) => {
    lastPut = await request.json()
    return HttpResponse.json({
      provider: 'openai',
      auth_type: 'api_key',
      masked_hint: 'sk-…1234',
      status: 'active',
      updated_at: '2026-06-19T00:00:00Z',
    })
  }),
  http.delete(`${PATH}/openai`, () => {
    deleted = true
    return new HttpResponse(null, { status: 204 })
  }),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
  creds = []
  lastPut = null
  deleted = false
  useAuthStore.setState({ accessToken: 'test-token', user: null })
})
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
})
afterAll(() => server.close())

function renderIt() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ExternalModelSettings />
    </QueryClientProvider>,
  )
}

describe('ExternalModelSettings', () => {
  it('saves a new OpenAI API key', async () => {
    const user = userEvent.setup()
    renderIt()
    await user.type(screen.getByLabelText(/^api key$/i), 'sk-mytestkey123')
    await user.click(screen.getByRole('button', { name: /save key/i }))

    expect(await screen.findByText(/saved/i)).toBeInTheDocument()
    expect(lastPut).toMatchObject({ provider: 'openai', auth_type: 'api_key', secret: 'sk-mytestkey123' })
  })

  it('shows the masked existing key and removes it', async () => {
    creds = [
      {
        provider: 'openai',
        auth_type: 'api_key',
        masked_hint: 'sk-…1234',
        status: 'active',
        updated_at: '2026-06-19T00:00:00Z',
      },
    ]
    const user = userEvent.setup()
    renderIt()
    expect(await screen.findByText('sk-…1234')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /remove/i }))
    await waitFor(() => expect(deleted).toBe(true))
    expect(await screen.findByText(/removed/i)).toBeInTheDocument()
  })

  it('saves a Codex subscription credential', async () => {
    server.use(
      http.put(PATH, async ({ request }) => {
        lastPut = await request.json()
        return HttpResponse.json({
          provider: 'codex',
          auth_type: 'oauth_token',
          masked_hint: '…NEW',
          status: 'active',
          updated_at: '2026-06-19T00:00:00Z',
        })
      }),
    )
    const user = userEvent.setup()
    renderIt()
    await user.type(screen.getByLabelText(/auth\.json/i), 'codex-token-blob')
    await user.click(screen.getByRole('button', { name: /save subscription/i }))

    expect(await screen.findByText(/codex subscription saved/i)).toBeInTheDocument()
    expect(lastPut).toMatchObject({
      provider: 'codex',
      auth_type: 'oauth_token',
      secret: 'codex-token-blob',
    })
  })

  it('explains when the server has not enabled external credentials (503)', async () => {
    server.use(
      http.put(PATH, () => HttpResponse.json({ detail: 'not configured' }, { status: 503 })),
    )
    const user = userEvent.setup()
    renderIt()
    await user.type(screen.getByLabelText(/^api key$/i), 'sk-x')
    await user.click(screen.getByRole('button', { name: /save key/i }))

    expect(await screen.findByText(/not enabled external credentials/i)).toBeInTheDocument()
  })
})
