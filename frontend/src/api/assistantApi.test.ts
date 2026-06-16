import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { assistantApi } from './assistantApi'

const BASE = 'http://localhost:8000/api/v1'

const server = setupServer(
  http.post(`${BASE}/assistant/chat`, async ({ request }) => {
    const auth = request.headers.get('authorization')
    const body = await request.json() as { message: string; session_id?: string }
    return HttpResponse.json({
      session_id: body.session_id ?? 'session-1',
      message: `${auth ?? 'no-auth'}:${body.message}`,
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
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
})
afterAll(() => server.close())

describe('assistantApi', () => {
  it('posts chat messages with auth and returns the assistant response', async () => {
    const response = await assistantApi.chat({ message: 'hello', session_id: 'session-1' })

    expect(response.status).toBe(200)
    expect(response.data.session_id).toBe('session-1')
    expect(response.data.message).toBe('Bearer test-token:hello')
  })
})
