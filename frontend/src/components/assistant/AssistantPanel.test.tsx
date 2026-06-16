import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { AssistantPanel } from './AssistantPanel'

const BASE = 'http://localhost:8000/api/v1'

const server = setupServer(
  http.post(`${BASE}/assistant/chat`, async ({ request }) => {
    const body = await request.json() as { message: string; session_id?: string }
    return HttpResponse.json({
      session_id: body.session_id ?? 'session-1',
      message: `Done: ${body.message}`,
      tool_calls: [],
      tool_results: [],
    })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
  useAuthStore.setState({ accessToken: 'test-token' })
})
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
})
afterAll(() => server.close())

function renderAssistantPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AssistantPanel />
    </QueryClientProvider>,
  )
}

describe('AssistantPanel', () => {
  it('opens inside the app shell and sends a chat message', async () => {
    renderAssistantPanel()

    await userEvent.click(screen.getByRole('button', { name: /open assistant/i }))
    expect(screen.getByRole('region', { name: /clouddrive assistant/i })).toBeInTheDocument()

    const input = screen.getByLabelText(/assistant message/i)
    await userEvent.type(input, 'hello')
    await userEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByText('Done: hello')).toBeInTheDocument()
    })
  })

  it('renders backend errors as assistant messages', async () => {
    server.use(
      http.post(`${BASE}/assistant/chat`, () =>
        HttpResponse.json(
          { error: { code: 'ASSISTANT_UNAVAILABLE', message: 'Assistant unavailable', details: {} } },
          { status: 503 },
        ),
      ),
    )
    renderAssistantPanel()

    await userEvent.click(screen.getByRole('button', { name: /open assistant/i }))
    await userEvent.type(screen.getByLabelText(/assistant message/i), 'hello')
    await userEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByText('Assistant is unavailable right now.')).toBeInTheDocument()
    })
  })
})
