/**
 * Tests for shareApi — proposal.md §5.2 功能 1–5
 *
 * 覆蓋功能：
 *   - 分享給指定使用者 (POST /share/items/:id)
 *   - 移除分享 (DELETE /share/items/:id/users/:userId)
 *   - 查看分享給我的項目 (GET /share/shared-with-me)
 *   - 建立公開分享連結 (POST /share/items/:id/links)
 *   - 建立含密碼與到期時間的連結
 *   - 驗證分享連結 (POST /share/links/validate)
 *   - 停用分享連結 (DELETE /share/links/:id)
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { shareApi } from './shareApi'

const BASE = 'http://localhost:8000/api/v1'

const MOCK_SHARE = {
  id: 'share-1',
  item_id: 'file-1',
  owner_id: 'u1',
  target_user_id: 'u2',
  permission: 'viewer',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const MOCK_LINK = {
  id: 'link-1',
  item_id: 'file-1',
  token: 'public-tok-abc',
  permission: 'viewer',
  expires_at: null,
  is_active: true,
  created_by: 'u1',
  created_at: '2024-01-01T00:00:00Z',
}

const server = setupServer(
  http.post(`${BASE}/share/items/:id`, async ({ params, request }) => {
    const body = await request.json() as Record<string, string>
    if (body.target_email === 'notfound@test.com') {
      return HttpResponse.json(
        { code: 'NOT_FOUND', message: 'User not found' },
        { status: 404 },
      )
    }
    return HttpResponse.json(
      { ...MOCK_SHARE, item_id: params.id as string, permission: body.permission },
      { status: 201 },
    )
  }),

  http.delete(`${BASE}/share/items/:id/users/:userId`, () =>
    new HttpResponse(null, { status: 204 }),
  ),

  http.get(`${BASE}/share/shared-with-me`, ({ request }) => {
    const url = new URL(request.url)
    return HttpResponse.json({
      items: [MOCK_SHARE],
      total: 1,
      page: Number(url.searchParams.get('page') ?? 1),
      page_size: Number(url.searchParams.get('page_size') ?? 20),
      pages: 1,
    })
  }),

  http.post(`${BASE}/share/items/:id/links`, async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json(
      {
        ...MOCK_LINK,
        item_id: params.id as string,
        permission: body.permission,
        expires_at: body.expires_at ?? null,
      },
      { status: 201 },
    )
  }),

  http.post(`${BASE}/share/links/validate`, ({ request }) => {
    const url = new URL(request.url)
    const token = url.searchParams.get('token')
    if (token !== 'public-tok-abc') {
      return HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Link not found or inactive', details: {} } },
        { status: 404 },
      )
    }
    return HttpResponse.json(MOCK_LINK)
  }),

  http.delete(`${BASE}/share/links/:id`, () => new HttpResponse(null, { status: 204 })),

  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  useAuthStore.setState({ accessToken: 'test-token' })
})
afterAll(() => server.close())

// ── 分享給指定使用者 ──────────────────────────────────────────────────────────

describe('shareItem (POST /share/items/:id)', () => {
  it('sends target_email and permission in body, returns 201', async () => {
    const res = await shareApi.shareItem('file-1', 'bob@example.com', 'viewer')
    expect(res.status).toBe(201)
    expect(res.data.permission).toBe('viewer')
    expect(res.data.item_id).toBe('file-1')
  })

  it('sends correct permission level', async () => {
    let capturedBody: unknown
    server.use(
      http.post(`${BASE}/share/items/:id`, async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json(MOCK_SHARE, { status: 201 })
      }),
    )
    await shareApi.shareItem('file-1', 'bob@example.com', 'editor')
    expect(capturedBody).toMatchObject({ target_email: 'bob@example.com', permission: 'editor' })
  })

  it('rejects with 404 when target user not found', async () => {
    await expect(
      shareApi.shareItem('file-1', 'notfound@test.com', 'viewer'),
    ).rejects.toMatchObject({ status: 404, code: 'NOT_FOUND' })
  })
})

// ── 移除分享 ──────────────────────────────────────────────────────────────────

describe('removeShare (DELETE /share/items/:id/users/:userId)', () => {
  it('sends DELETE to correct URL and returns 204', async () => {
    const res = await shareApi.removeShare('file-1', 'u2')
    expect(res.status).toBe(204)
  })

  it('includes both item id and user id in URL', async () => {
    let capturedUrl = ''
    server.use(
      http.delete(`${BASE}/share/items/:id/users/:userId`, ({ request }) => {
        capturedUrl = request.url
        return new HttpResponse(null, { status: 204 })
      }),
    )
    await shareApi.removeShare('file-99', 'user-42')
    expect(capturedUrl).toContain('/share/items/file-99/users/user-42')
  })
})

// ── 查看分享給我的項目 ────────────────────────────────────────────────────────

describe('sharedWithMe (GET /share/shared-with-me)', () => {
  it('returns paginated list of shares', async () => {
    const res = await shareApi.sharedWithMe()
    expect(res.status).toBe(200)
    expect(res.data.items).toHaveLength(1)
    expect(res.data.items[0].target_user_id).toBe('u2')
  })

  it('sends page and page_size params', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/share/shared-with-me`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ items: [], total: 0, page: 2, page_size: 10, pages: 0 })
      }),
    )
    await shareApi.sharedWithMe(2, 10)
    expect(capturedUrl).toContain('page=2')
    expect(capturedUrl).toContain('page_size=10')
  })
})

// ── 建立公開分享連結 ──────────────────────────────────────────────────────────

describe('createLink (POST /share/items/:id/links)', () => {
  it('creates a link with viewer permission', async () => {
    const res = await shareApi.createLink('file-1', 'viewer')
    expect(res.status).toBe(201)
    expect(res.data.is_active).toBe(true)
    expect(res.data.permission).toBe('viewer')
    expect(res.data.token).toBeTruthy()
  })

  it('sends password and expires_at when provided', async () => {
    let capturedBody: unknown
    server.use(
      http.post(`${BASE}/share/items/:id/links`, async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json(MOCK_LINK, { status: 201 })
      }),
    )
    await shareApi.createLink('file-1', 'viewer', {
      password: 'secret123',
      expires_at: '2025-12-31T00:00:00Z',
    })
    expect(capturedBody).toMatchObject({
      permission: 'viewer',
      password: 'secret123',
      expires_at: '2025-12-31T00:00:00Z',
    })
  })

  it('link has null expires_at when not set', async () => {
    const res = await shareApi.createLink('file-1', 'viewer')
    expect(res.data.expires_at).toBeNull()
  })
})

// ── 驗證分享連結 ──────────────────────────────────────────────────────────────

describe('validateLink (POST /share/links/validate)', () => {
  it('returns link info for valid token', async () => {
    const res = await shareApi.validateLink('public-tok-abc')
    expect(res.status).toBe(200)
    expect(res.data.is_active).toBe(true)
    expect(res.data.token).toBe('public-tok-abc')
  })

  it('rejects with 404 for invalid token', async () => {
    await expect(
      shareApi.validateLink('bad-token'),
    ).rejects.toMatchObject({ status: 404 })
  })

  it('sends token as query param', async () => {
    let capturedUrl = ''
    server.use(
      http.post(`${BASE}/share/links/validate`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json(MOCK_LINK)
      }),
    )
    await shareApi.validateLink('public-tok-abc')
    expect(capturedUrl).toContain('token=public-tok-abc')
  })
})

// ── 停用分享連結 ──────────────────────────────────────────────────────────────

describe('deactivateLink (DELETE /share/links/:id)', () => {
  it('sends DELETE and returns 204', async () => {
    const res = await shareApi.deactivateLink('link-1')
    expect(res.status).toBe(204)
  })

  it('calls the correct link URL', async () => {
    let capturedUrl = ''
    server.use(
      http.delete(`${BASE}/share/links/:id`, ({ request }) => {
        capturedUrl = request.url
        return new HttpResponse(null, { status: 204 })
      }),
    )
    await shareApi.deactivateLink('link-99')
    expect(capturedUrl).toContain('/share/links/link-99')
  })
})
