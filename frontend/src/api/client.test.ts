import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { api } from './client'

const BASE = 'http://localhost:8000/api/v1'

const server = setupServer(
  http.get(`${BASE}/users/me`, ({ request }) => {
    const auth = request.headers.get('Authorization')
    if (!auth?.startsWith('Bearer valid-token')) {
      return HttpResponse.json({ code: 'UNAUTHORIZED', message: 'Unauthorized' }, { status: 401 })
    }
    return HttpResponse.json({ id: 'u1', email: 'a@test.com', username: 'alice' })
  }),

  http.post(`${BASE}/auth/refresh`, () => {
    return HttpResponse.json({ access_token: 'refreshed-token', token_type: 'bearer' })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null })
})
afterAll(() => server.close())

describe('Authorization header', () => {
  it('attaches bearer token when store has one', async () => {
    useAuthStore.setState({ accessToken: 'valid-token' })
    const res = await api.get('/users/me')
    expect(res.status).toBe(200)
  })

  it('omits Authorization when no token in store', async () => {
    // server returns 401 when no auth header — then refresh kicks in
    // Simulate refresh failure to see store cleared
    server.use(
      http.post(`${BASE}/auth/refresh`, () => {
        return HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 })
      }),
    )
    await expect(api.get('/users/me')).rejects.toMatchObject({ status: 401 })
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})

describe('401 refresh flow', () => {
  beforeEach(() => {
    // Token is expired — server returns 401 until refreshed
    useAuthStore.setState({ accessToken: 'expired-token' })
  })

  it('refreshes token and retries on 401', async () => {
    // After refresh, the retried request will have 'refreshed-token'
    // which starts with 'Bearer valid-' — but 'refreshed-token' != 'valid-token'
    // Adjust server to accept refreshed-token too
    server.use(
      http.get(`${BASE}/users/me`, ({ request }) => {
        const auth = request.headers.get('Authorization')
        if (auth === 'Bearer expired-token') {
          return HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 })
        }
        if (auth === 'Bearer refreshed-token') {
          return HttpResponse.json({ id: 'u1', email: 'a@test.com', username: 'alice' })
        }
        return HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 })
      }),
    )
    const res = await api.get('/users/me')
    expect(res.status).toBe(200)
    expect(useAuthStore.getState().accessToken).toBe('refreshed-token')
  })

  it('shares one refresh request across simultaneous 401 responses', async () => {
    let refreshCount = 0
    server.use(
      http.get(`${BASE}/users/me`, ({ request }) => {
        const auth = request.headers.get('Authorization')
        if (auth === 'Bearer refreshed-token') {
          return HttpResponse.json({ id: 'u1', email: 'a@test.com', username: 'alice' })
        }
        return HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 })
      }),
      http.post(`${BASE}/auth/refresh`, async () => {
        refreshCount += 1
        await new Promise((resolve) => setTimeout(resolve, 20))
        return HttpResponse.json({ access_token: 'refreshed-token', token_type: 'bearer' })
      }),
    )

    const [first, second] = await Promise.all([api.get('/users/me'), api.get('/users/me')])

    expect(first.status).toBe(200)
    expect(second.status).toBe(200)
    expect(refreshCount).toBe(1)
  })

  it('clears auth store when refresh fails', async () => {
    server.use(
      http.post(`${BASE}/auth/refresh`, () =>
        HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
      ),
    )
    await expect(api.get('/users/me')).rejects.toMatchObject({ status: 401 })
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})

describe('401 refresh retries a body request without dropping the body', () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: 'expired-token' })
  })

  it('re-sends the multipart body on the retried upload', async () => {
    // Regression: with the fetch adapter the FormData body was consumed by the
    // first (401) attempt, so the retry sent an empty body and the upload
    // failed as a spurious "Connection lost". The XHR adapter must re-serialize
    // the body on retry.
    let retriedBody: string | null = null
    server.use(
      http.post(`${BASE}/upload/simple`, async ({ request }) => {
        const auth = request.headers.get('Authorization')
        if (auth === 'Bearer expired-token') {
          return HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 })
        }
        // Read the raw multipart body (jsdom's formData() is unreliable here).
        retriedBody = await request.text()
        return HttpResponse.json({ id: 'item-1', name: 'note.txt' }, { status: 201 })
      }),
    )

    const form = new FormData()
    form.append('file', new File(['hello chunk world'], 'note.txt', { type: 'text/plain' }))
    // Uploads run on the XHR adapter (see uploadApi) — that's what makes the
    // retried request re-send the body rather than an empty one.
    const res = await api.post('/upload/simple', form, { adapter: 'xhr' })

    expect(res.status).toBe(201)
    // The retry must carry a non-empty multipart body. (jsdom+undici don't
    // round-trip a File's bytes or part headers, so we can only assert the
    // multipart envelope survived — but the bug dropped the body to empty,
    // which this still catches: an empty retry body has no boundary.)
    expect(retriedBody).toBeTruthy()
    expect((retriedBody as unknown as string).length).toBeGreaterThan(10)
    expect(retriedBody).toContain('formdata')
  })
})

describe('error conversion', () => {
  it('converts backend error response to ApiError shape', async () => {
    server.use(
      http.get(`${BASE}/users/me`, () =>
        HttpResponse.json({ code: 'NOT_FOUND', message: 'User not found' }, { status: 404 }),
      ),
    )
    useAuthStore.setState({ accessToken: 'valid-token' })
    await expect(api.get('/users/me')).rejects.toMatchObject({
      code: 'NOT_FOUND',
      message: 'User not found',
      status: 404,
    })
  })

  it('converts the backend nested error envelope', async () => {
    server.use(
      http.get(`${BASE}/users/me`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'EMAIL_ALREADY_EXISTS',
              message: 'Email already in use',
              details: { field: 'email' },
            },
          },
          { status: 409 },
        ),
      ),
    )
    useAuthStore.setState({ accessToken: 'valid-token' })
    await expect(api.get('/users/me')).rejects.toMatchObject({
      code: 'EMAIL_ALREADY_EXISTS',
      message: 'Email already in use',
      status: 409,
      details: { field: 'email' },
    })
  })
})

describe('AbortSignal', () => {
  it('cancels the request', async () => {
    const controller = new AbortController()
    server.use(
      http.get(`${BASE}/users/me`, async () => {
        await new Promise((r) => setTimeout(r, 500))
        return HttpResponse.json({})
      }),
    )
    useAuthStore.setState({ accessToken: 'valid-token' })
    const promise = api.get('/users/me', { signal: controller.signal })
    controller.abort()
    await expect(promise).rejects.toMatchObject({ code: 'CANCELED' })
  })
})
