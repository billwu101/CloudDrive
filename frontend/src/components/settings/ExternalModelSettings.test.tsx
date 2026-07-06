import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { ExternalModelSettings } from './ExternalModelSettings'

const BASE = 'http://localhost:8000/api/v1'
const PATH = `${BASE}/users/me/model-connections`

let connections: unknown[] = []
let lastPost: unknown = null
let deletedId: string | null = null

const server = setupServer(
  http.get(PATH, () => HttpResponse.json(connections)),
  http.post(PATH, async ({ request }) => {
    lastPost = await request.json()
    return HttpResponse.json({
      id: 'conn-1',
      label: 'My Gemini',
      kind: 'openai_compatible',
      base_url: 'https://g/v1',
      model: 'gemini-2.5-flash-lite',
      masked_hint: 'AIz…rQ4',
      status: 'active',
      updated_at: '2026-06-25T00:00:00Z',
    })
  }),
  http.delete(`${PATH}/conn-1`, () => {
    deletedId = 'conn-1'
    return new HttpResponse(null, { status: 204 })
  }),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
  connections = []
  lastPost = null
  deletedId = null
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
  it('adds a named connection with its own model and key', async () => {
    const user = userEvent.setup()
    renderIt()
    await user.type(screen.getByLabelText(/connection name/i), 'My Gemini')
    await user.type(screen.getByLabelText(/api key or token/i), 'AIza-test-key')
    await user.click(screen.getByRole('button', { name: /add connection/i }))

    expect(await screen.findByText(/connection added/i)).toBeInTheDocument()
    expect(lastPost).toMatchObject({ label: 'My Gemini', kind: 'openai_compatible', secret: 'AIza-test-key' })
  })

  it('shows an existing connection masked and removes it', async () => {
    connections = [
      {
        id: 'conn-1',
        label: 'My Gemini',
        kind: 'openai_compatible',
        base_url: 'https://g/v1',
        model: 'gemini-2.5-flash-lite',
        masked_hint: 'AIz…rQ4',
        status: 'active',
        updated_at: '2026-06-25T00:00:00Z',
      },
    ]
    const user = userEvent.setup()
    renderIt()
    expect(await screen.findByText('AIz…rQ4')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /remove/i }))
    await waitFor(() => expect(deletedId).toBe('conn-1'))
    expect(await screen.findByText(/connection removed/i)).toBeInTheDocument()
  })

  it('explains when the server has not enabled model connections (503)', async () => {
    server.use(
      http.post(PATH, () => HttpResponse.json({ detail: 'not configured' }, { status: 503 })),
    )
    const user = userEvent.setup()
    renderIt()
    await user.type(screen.getByLabelText(/connection name/i), 'X')
    await user.type(screen.getByLabelText(/api key or token/i), 'sk-x')
    await user.click(screen.getByRole('button', { name: /add connection/i }))

    expect(await screen.findByText(/not enabled model connections/i)).toBeInTheDocument()
  })
})
