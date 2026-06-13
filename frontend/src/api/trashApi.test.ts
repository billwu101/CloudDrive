/**
 * Tests for trashApi — proposal.md §5.1 功能 9, 10
 *
 * 覆蓋功能：
 *   - 移動到垃圾桶 (POST /trash/items/:id)
 *   - 垃圾桶列表 (GET /trash)
 *   - 從垃圾桶還原 (POST /trash/items/:id/restore)
 *   - 永久刪除單一項目 (DELETE /trash/items/:id)
 *   - 清空垃圾桶 (DELETE /trash)
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { trashApi } from './trashApi'

const BASE = 'http://localhost:8000/api/v1'

const ACTIVE_ITEM = {
  id: 'file-1',
  owner_id: 'u1',
  parent_id: null,
  item_type: 'FILE',
  name: 'old.txt',
  mime_type: 'text/plain',
  extension: 'txt',
  size_bytes: 100,
  is_starred: false,
  is_deleted: false,
  deleted_at: null,
  created_by: 'u1',
  updated_by: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const TRASHED_ITEM = {
  ...ACTIVE_ITEM,
  is_deleted: true,
  deleted_at: '2024-06-01T00:00:00Z',
}

const server = setupServer(
  http.post(`${BASE}/trash/items/:id`, ({ params }) =>
    HttpResponse.json({ ...TRASHED_ITEM, id: params.id as string }),
  ),

  http.get(`${BASE}/trash`, ({ request }) => {
    const url = new URL(request.url)
    const page = Number(url.searchParams.get('page') ?? 1)
    const page_size = Number(url.searchParams.get('page_size') ?? 50)
    return HttpResponse.json({
      items: [TRASHED_ITEM],
      total: 1,
      page,
      page_size,
      pages: 1,
    })
  }),

  http.post(`${BASE}/trash/items/:id/restore`, ({ params }) =>
    HttpResponse.json({ ...ACTIVE_ITEM, id: params.id as string }),
  ),

  http.delete(`${BASE}/trash/items/:id`, () => new HttpResponse(null, { status: 204 })),

  http.delete(`${BASE}/trash`, () => new HttpResponse(null, { status: 204 })),

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

// ── 移動到垃圾桶 ──────────────────────────────────────────────────────────────

describe('moveToTrash (POST /trash/items/:id)', () => {
  it('sends POST to correct URL and returns trashed item', async () => {
    const res = await trashApi.moveToTrash('file-1')
    expect(res.status).toBe(200)
    expect(res.data.id).toBe('file-1')
    expect(res.data.is_deleted).toBe(true)
  })

  it('returned item has deleted_at timestamp', async () => {
    const res = await trashApi.moveToTrash('file-1')
    expect(res.data.deleted_at).not.toBeNull()
  })
})

// ── 垃圾桶列表 ────────────────────────────────────────────────────────────────

describe('listTrash (GET /trash)', () => {
  it('returns paginated list of trashed items', async () => {
    const res = await trashApi.listTrash()
    expect(res.status).toBe(200)
    expect(res.data.items).toHaveLength(1)
    expect(res.data.items[0].is_deleted).toBe(true)
  })

  it('sends page and page_size as query params', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/trash`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ items: [], total: 0, page: 2, page_size: 10, pages: 0 })
      }),
    )
    await trashApi.listTrash(2, 10)
    expect(capturedUrl).toContain('page=2')
    expect(capturedUrl).toContain('page_size=10')
  })
})

// ── 從垃圾桶還原 ──────────────────────────────────────────────────────────────

describe('restore (POST /trash/items/:id/restore)', () => {
  it('sends POST to restore URL and returns active item', async () => {
    const res = await trashApi.restore('file-1')
    expect(res.status).toBe(200)
    expect(res.data.id).toBe('file-1')
    expect(res.data.is_deleted).toBe(false)
  })

  it('restored item has null deleted_at', async () => {
    const res = await trashApi.restore('file-1')
    expect(res.data.deleted_at).toBeNull()
  })
})

// ── 永久刪除單一項目 ──────────────────────────────────────────────────────────

describe('permanentDelete (DELETE /trash/items/:id)', () => {
  it('sends DELETE and returns 204', async () => {
    const res = await trashApi.permanentDelete('file-1')
    expect(res.status).toBe(204)
  })

  it('calls the correct item-specific URL', async () => {
    let capturedUrl = ''
    server.use(
      http.delete(`${BASE}/trash/items/:id`, ({ request }) => {
        capturedUrl = request.url
        return new HttpResponse(null, { status: 204 })
      }),
    )
    await trashApi.permanentDelete('file-99')
    expect(capturedUrl).toContain('/trash/items/file-99')
    expect(capturedUrl).not.toContain('/trash/items/file-99/') // not the emptyTrash URL
  })
})

// ── 清空垃圾桶 ────────────────────────────────────────────────────────────────

describe('emptyTrash (DELETE /trash)', () => {
  it('sends DELETE to /trash and returns 204', async () => {
    const res = await trashApi.emptyTrash()
    expect(res.status).toBe(204)
  })
})
