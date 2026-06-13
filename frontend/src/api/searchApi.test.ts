/**
 * Tests for searchApi — proposal.md §5.1 功能 11
 *
 * 覆蓋功能：
 *   - 關鍵字搜尋 (GET /search?q=...)
 *   - 依類型過濾 (item_type=file|folder)
 *   - 依 MIME 類型過濾 (mime_type=...)
 *   - 分頁參數
 *   - 無結果回傳空陣列
 *   - 請求取消
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { searchApi } from './searchApi'

const BASE = 'http://localhost:8000/api/v1'

const MOCK_FILE = {
  id: 'file-1',
  owner_id: 'u1',
  parent_id: null,
  item_type: 'FILE',
  name: 'quarterly_report.pdf',
  mime_type: 'application/pdf',
  extension: 'pdf',
  size_bytes: 204800,
  is_starred: false,
  is_deleted: false,
  deleted_at: null,
  created_by: 'u1',
  updated_by: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const server = setupServer(
  http.get(`${BASE}/search`, ({ request }) => {
    const url = new URL(request.url)
    const q = url.searchParams.get('q') ?? ''
    const itemType = url.searchParams.get('item_type')

    if (!q) return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })

    let items = q.toLowerCase().includes('report') ? [MOCK_FILE] : []
    if (itemType === 'folder') items = []

    return HttpResponse.json({ items, total: items.length, page: 1, page_size: 20, pages: items.length > 0 ? 1 : 0 })
  }),

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

// ── 關鍵字搜尋 ────────────────────────────────────────────────────────────────

describe('search (GET /search)', () => {
  it('sends q as query param and returns matching items', async () => {
    const res = await searchApi.search({ q: 'quarterly_report' })
    expect(res.status).toBe(200)
    expect(res.data.items).toHaveLength(1)
    expect(res.data.items[0].name).toBe('quarterly_report.pdf')
  })

  it('returns empty items array when nothing matches', async () => {
    const res = await searchApi.search({ q: 'xyznonexistent' })
    expect(res.data.items).toHaveLength(0)
    expect(res.data.total).toBe(0)
  })

  it('sends q param in request URL', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/search`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
      }),
    )
    await searchApi.search({ q: 'hello world' })
    expect(capturedUrl).toContain('q=')
    expect(new URL(capturedUrl).searchParams.get('q')).toBe('hello world')
  })
})

// ── 依類型過濾 ────────────────────────────────────────────────────────────────

describe('search with item_type filter', () => {
  it('sends item_type=file param', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/search`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
      }),
    )
    await searchApi.search({ q: 'report', item_type: 'file' })
    expect(capturedUrl).toContain('item_type=file')
  })

  it('sends item_type=folder param', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/search`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
      }),
    )
    await searchApi.search({ q: 'report', item_type: 'folder' })
    expect(capturedUrl).toContain('item_type=folder')
  })

  it('filters by folder type returns no file results', async () => {
    const res = await searchApi.search({ q: 'report', item_type: 'folder' })
    expect(res.data.items).toHaveLength(0)
  })
})

// ── 依 MIME 類型過濾 ──────────────────────────────────────────────────────────

describe('search with mime_type filter', () => {
  it('sends mime_type param in request', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/search`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
      }),
    )
    await searchApi.search({ q: 'report', mime_type: 'application/pdf' })
    expect(capturedUrl).toContain('mime_type=application%2Fpdf')
  })
})

// ── 分頁 ──────────────────────────────────────────────────────────────────────

describe('search pagination', () => {
  it('sends page and page_size params', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/search`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ items: [], total: 0, page: 2, page_size: 10, pages: 0 })
      }),
    )
    await searchApi.search({ q: 'doc', page: 2, page_size: 10 })
    expect(capturedUrl).toContain('page=2')
    expect(capturedUrl).toContain('page_size=10')
  })

  it('response includes pagination metadata', async () => {
    const res = await searchApi.search({ q: 'quarterly_report' })
    expect(res.data).toMatchObject({
      items: expect.any(Array),
      total: expect.any(Number),
      page: expect.any(Number),
      page_size: expect.any(Number),
      pages: expect.any(Number),
    })
  })
})

// ── 請求取消 ──────────────────────────────────────────────────────────────────

describe('search with AbortSignal', () => {
  it('cancels the search request', async () => {
    const controller = new AbortController()
    server.use(
      http.get(`${BASE}/search`, async () => {
        await new Promise((r) => setTimeout(r, 500))
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 0 })
      }),
    )
    const promise = searchApi.search({ q: 'test', signal: controller.signal })
    controller.abort()
    await expect(promise).rejects.toMatchObject({ code: 'CANCELED' })
  })
})
