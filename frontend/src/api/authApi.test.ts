/**
 * Tests for authApi — proposal.md §5.1 功能 1, 2, 16
 *
 * 覆蓋功能：
 *   - 使用者註冊 (POST /auth/register)
 *   - 使用者登入 (POST /auth/login)
 *   - 使用者登出 (POST /auth/logout)
 *   - 取得目前使用者 (GET /users/me)
 *   - 更新名稱、email 與密碼
 *   - 容量統計 (GET /users/me/quota)
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { authApi } from './authApi'

const BASE = 'http://localhost:8000/api/v1'

const MOCK_USER = {
  id: 'u1',
  email: 'alice@example.com',
  username: 'alice',
  avatar_url: null,
  quota_bytes: 15 * 1024 ** 3,
  used_bytes: 1024,
  is_active: true,
  is_admin: false,
  must_change_password: false,
  created_at: '2024-01-01T00:00:00Z',
}

const MOCK_QUOTA = {
  quota_bytes: 15 * 1024 ** 3,
  used_bytes: 1024,
  available_bytes: 15 * 1024 ** 3 - 1024,
  used_percent: 0.0001,
}

const server = setupServer(
  http.post(`${BASE}/auth/register`, async ({ request }) => {
    const body = await request.json() as Record<string, string>
    if (body.email === 'exists@example.com') {
      return HttpResponse.json(
        { code: 'EMAIL_ALREADY_EXISTS', message: 'Email already registered' },
        { status: 409 },
      )
    }
    return HttpResponse.json({ ...MOCK_USER, email: body.email, username: body.username }, { status: 201 })
  }),

  http.post(`${BASE}/auth/login`, async ({ request }) => {
    const body = await request.json() as Record<string, string>
    if (body.password === 'wrongpassword') {
      return HttpResponse.json(
        { code: 'INVALID_CREDENTIALS', message: 'Invalid credentials' },
        { status: 401 },
      )
    }
    return HttpResponse.json({ access_token: 'tok-abc', token_type: 'bearer' })
  }),

  http.post(`${BASE}/auth/forgot-password`, async ({ request }) => {
    const body = (await request.json()) as { email: string }
    // Non-enumerable: same response regardless of whether the email exists.
    return HttpResponse.json({
      message: 'If an account exists for that email, a reset password has been sent.',
      echo_email: body.email,
    })
  }),

  http.post(`${BASE}/auth/logout`, () => new HttpResponse(null, { status: 204 })),

  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),

  http.get(`${BASE}/users/me`, () => HttpResponse.json(MOCK_USER)),

  http.patch(`${BASE}/users/me`, async ({ request }) => {
    const body = await request.json() as { username: string }
    return HttpResponse.json({ ...MOCK_USER, username: body.username })
  }),

  http.patch(`${BASE}/users/me/email`, async ({ request }) => {
    const body = await request.json() as { email: string }
    return HttpResponse.json({ ...MOCK_USER, email: body.email })
  }),

  http.patch(`${BASE}/users/me/password`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${BASE}/users/me/quota`, () => HttpResponse.json(MOCK_QUOTA)),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  useAuthStore.setState({ accessToken: 'test-token' })
})
afterAll(() => server.close())

// ── 使用者註冊 ────────────────────────────────────────────────────────────────

describe('register (POST /auth/register)', () => {
  it('sends email, username, password and returns user', async () => {
    const res = await authApi.register('alice@example.com', 'alice', 'Pass123!')
    expect(res.status).toBe(201)
    expect(res.data.email).toBe('alice@example.com')
    expect(res.data.username).toBe('alice')
  })

  it('rejects with 409 when email already exists', async () => {
    await expect(
      authApi.register('exists@example.com', 'dup', 'Pass123!'),
    ).rejects.toMatchObject({ status: 409, code: 'EMAIL_ALREADY_EXISTS' })
  })
})

// ── 使用者登入 ────────────────────────────────────────────────────────────────

describe('login (POST /auth/login)', () => {
  it('sends credentials and returns access token', async () => {
    const res = await authApi.login('alice@example.com', 'Pass123!')
    expect(res.status).toBe(200)
    expect(res.data.access_token).toBe('tok-abc')
    expect(res.data.token_type).toBe('bearer')
  })

  it('rejects with 401 on wrong password', async () => {
    await expect(
      authApi.login('alice@example.com', 'wrongpassword'),
    ).rejects.toMatchObject({ status: 401, code: 'INVALID_CREDENTIALS' })
  })

  it('response body does NOT contain refresh_token', async () => {
    const res = await authApi.login('alice@example.com', 'Pass123!')
    expect(res.data).not.toHaveProperty('refresh_token')
  })
})

// ── 忘記密碼 ──────────────────────────────────────────────────────────────────

describe('forgotPassword (POST /auth/forgot-password)', () => {
  it('sends the email and returns a generic message', async () => {
    const res = await authApi.forgotPassword('alice@example.com')
    expect(res.status).toBe(200)
    expect(res.data.message).toMatch(/if an account exists/i)
  })

  it('posts the email in the request body', async () => {
    const res = await authApi.forgotPassword('alice@example.com')
    expect((res.data as { echo_email: string }).echo_email).toBe('alice@example.com')
  })
})

// ── 使用者登出 ────────────────────────────────────────────────────────────────

describe('logout (POST /auth/logout)', () => {
  it('returns 204 No Content', async () => {
    const res = await authApi.logout()
    expect(res.status).toBe(204)
  })
})

// ── 取得目前使用者 ────────────────────────────────────────────────────────────

describe('me (GET /users/me)', () => {
  it('returns current user profile', async () => {
    const res = await authApi.me()
    expect(res.status).toBe(200)
    expect(res.data.email).toBe('alice@example.com')
    expect(res.data.id).toBe('u1')
  })

  it('response does NOT expose password or token fields', async () => {
    const res = await authApi.me()
    expect(res.data).not.toHaveProperty('password')
    expect(res.data).not.toHaveProperty('password_hash')
    expect(res.data).not.toHaveProperty('access_token')
  })
})

// ── 帳號設定 ──────────────────────────────────────────────────────────────────

describe('account settings', () => {
  it('updates the username', async () => {
    const res = await authApi.updateUsername('new-name')
    expect(res.status).toBe(200)
    expect(res.data.username).toBe('new-name')
  })

  it('updates the email', async () => {
    const res = await authApi.updateEmail('new@example.com')
    expect(res.status).toBe(200)
    expect(res.data.email).toBe('new@example.com')
  })

  it('changes the password', async () => {
    const res = await authApi.changePassword('old-password', 'new-password')
    expect(res.status).toBe(204)
  })
})

// ── 容量統計 ──────────────────────────────────────────────────────────────────

describe('quota (GET /users/me/quota)', () => {
  it('returns quota stats with required fields', async () => {
    const res = await authApi.quota()
    expect(res.status).toBe(200)
    expect(res.data).toMatchObject({
      quota_bytes: expect.any(Number),
      used_bytes: expect.any(Number),
      available_bytes: expect.any(Number),
      used_percent: expect.any(Number),
    })
  })

  it('available_bytes equals quota_bytes minus used_bytes', async () => {
    const res = await authApi.quota()
    const { quota_bytes, used_bytes, available_bytes } = res.data
    expect(available_bytes).toBe(quota_bytes - used_bytes)
  })
})
