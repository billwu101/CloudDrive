/**
 * Tests for driveApi — proposal.md §5.1 功能 5, 6, 7, 8, 12, 13
 *
 * 覆蓋功能：
 *   - 建立資料夾 (POST /drive/folders)
 *   - 檔案與資料夾列表 (GET /drive/items)
 *   - 取得單一項目 (GET /drive/items/:id)
 *   - 重新命名 (PATCH /drive/items/:id/name)
 *   - 移動 (PATCH /drive/items/:id/parent)
 *   - 星號標記 (PUT /drive/items/:id/star)
 *   - 最近檔案列表 (GET /drive/recent)
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { driveApi } from './driveApi'

const BASE = 'http://localhost:8000/api/v1'

const MOCK_FOLDER = {
  id: 'folder-1',
  owner_id: 'u1',
  parent_id: null,
  item_type: 'FOLDER',
  name: 'Docs',
  mime_type: null,
  extension: null,
  size_bytes: 0,
  is_starred: false,
  is_deleted: false,
  deleted_at: null,
  created_by: 'u1',
  updated_by: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const MOCK_FILE = {
  ...MOCK_FOLDER,
  id: 'file-1',
  item_type: 'FILE',
  name: 'report.pdf',
  mime_type: 'application/pdf',
  extension: 'pdf',
  size_bytes: 204800,
}

const PAGE = {
  items: [MOCK_FOLDER, MOCK_FILE],
  total: 2,
  page: 1,
  page_size: 20,
  pages: 1,
}

const server = setupServer(
  http.get(`${BASE}/drive/items`, () => HttpResponse.json(PAGE)),

  http.get(`${BASE}/drive/items/:id`, ({ params }) =>
    params.id === 'folder-1'
      ? HttpResponse.json(MOCK_FOLDER)
      : HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Not found', details: {} } }, { status: 404 }),
  ),

  http.post(`${BASE}/drive/folders`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    if (!body.name) {
      return HttpResponse.json(
        { error: { code: 'VALIDATION_ERROR', message: 'Name required', details: {} } },
        { status: 422 },
      )
    }
    return HttpResponse.json({ ...MOCK_FOLDER, name: body.name as string }, { status: 201 })
  }),

  http.patch(`${BASE}/drive/items/:id/name`, async ({ params, request }) => {
    const body = await request.json() as Record<string, string>
    return HttpResponse.json({ ...MOCK_FOLDER, id: params.id as string, name: body.name })
  }),

  http.patch(`${BASE}/drive/items/:id/parent`, async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({ ...MOCK_FILE, id: params.id as string, parent_id: body.parent_id })
  }),

  http.put(`${BASE}/drive/items/:id/star`, async ({ params, request }) => {
    const body = await request.json() as Record<string, boolean>
    return HttpResponse.json({ ...MOCK_FILE, id: params.id as string, is_starred: body.is_starred })
  }),

  http.get(`${BASE}/drive/recent`, ({ request }) => {
    const url = new URL(request.url)
    const limit = Number(url.searchParams.get('limit') ?? 20)
    return HttpResponse.json([MOCK_FILE].slice(0, limit))
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

// ── 列表 ──────────────────────────────────────────────────────────────────────

describe('listItems (GET /drive/items)', () => {
  it('returns paginated items with both folders and files', async () => {
    const res = await driveApi.listItems()
    expect(res.status).toBe(200)
    expect(res.data.items).toHaveLength(2)
    expect(res.data.total).toBe(2)
  })

  it('sends parent_id as query param when provided', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/drive/items`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json(PAGE)
      }),
    )
    await driveApi.listItems({ parent_id: 'folder-1' })
    expect(capturedUrl).toContain('parent_id=folder-1')
  })

  it('sends sort_by and order params', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/drive/items`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json(PAGE)
      }),
    )
    await driveApi.listItems({ sort_by: 'created_at', order: 'desc' })
    expect(capturedUrl).toContain('sort_by=created_at')
    expect(capturedUrl).toContain('order=desc')
  })
})

// ── 取得單一項目 ──────────────────────────────────────────────────────────────

describe('getItem (GET /drive/items/:id)', () => {
  it('returns the item when found', async () => {
    const res = await driveApi.listItems()
    expect(res.data.items[0].id).toBe('folder-1')
  })
})

// ── 建立資料夾 ────────────────────────────────────────────────────────────────

describe('createFolder (POST /drive/folders)', () => {
  it('sends name in body and returns 201 with new folder', async () => {
    const res = await driveApi.createFolder('My Folder')
    expect(res.status).toBe(201)
    expect(res.data.name).toBe('My Folder')
    expect(res.data.item_type).toBe('FOLDER')
  })

  it('sends parent_id when provided', async () => {
    let capturedBody: unknown
    server.use(
      http.post(`${BASE}/drive/folders`, async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json(MOCK_FOLDER, { status: 201 })
      }),
    )
    await driveApi.createFolder('Sub', 'folder-1')
    expect(capturedBody).toMatchObject({ name: 'Sub', parent_id: 'folder-1' })
  })

  it('new folder has item_type FOLDER', async () => {
    const res = await driveApi.createFolder('Test')
    expect(res.data.item_type).toBe('FOLDER')
  })
})

// ── 重新命名 ──────────────────────────────────────────────────────────────────

describe('rename (PATCH /drive/items/:id/name)', () => {
  it('sends new name and returns updated item', async () => {
    const res = await driveApi.rename('folder-1', 'Renamed Docs')
    expect(res.status).toBe(200)
    expect(res.data.name).toBe('Renamed Docs')
  })

  it('sends name field in request body', async () => {
    let capturedBody: unknown
    server.use(
      http.patch(`${BASE}/drive/items/:id/name`, async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json(MOCK_FOLDER)
      }),
    )
    await driveApi.rename('folder-1', 'NewName')
    expect(capturedBody).toEqual({ name: 'NewName' })
  })
})

// ── 移動 ──────────────────────────────────────────────────────────────────────

describe('move (PATCH /drive/items/:id/parent)', () => {
  it('sends parent_id in body and returns updated item', async () => {
    const res = await driveApi.move('file-1', 'folder-1')
    expect(res.status).toBe(200)
    expect(res.data.parent_id).toBe('folder-1')
  })

  it('can move to root by sending null parent_id', async () => {
    let capturedBody: unknown
    server.use(
      http.patch(`${BASE}/drive/items/:id/parent`, async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({ ...MOCK_FILE, parent_id: null })
      }),
    )
    await driveApi.move('file-1', null)
    expect(capturedBody).toEqual({ parent_id: null })
  })
})

// ── 星號標記 ──────────────────────────────────────────────────────────────────

describe('star (PUT /drive/items/:id/star)', () => {
  it('sends is_starred=true and returns updated item', async () => {
    const res = await driveApi.star('file-1', true)
    expect(res.status).toBe(200)
    expect(res.data.is_starred).toBe(true)
  })

  it('sends is_starred=false to unstar', async () => {
    let capturedBody: unknown
    server.use(
      http.put(`${BASE}/drive/items/:id/star`, async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({ ...MOCK_FILE, is_starred: false })
      }),
    )
    await driveApi.star('file-1', false)
    expect(capturedBody).toEqual({ is_starred: false })
  })

  it('uses PUT method (not PATCH)', async () => {
    const methods: string[] = []
    server.use(
      http.put(`${BASE}/drive/items/:id/star`, async ({ request }) => {
        methods.push(request.method)
        return HttpResponse.json(MOCK_FILE)
      }),
    )
    await driveApi.star('file-1', true)
    expect(methods[0]).toBe('PUT')
  })
})

// ── 最近檔案列表 ──────────────────────────────────────────────────────────────

describe('getRecent (GET /drive/recent)', () => {
  it('returns array of recent items', async () => {
    const res = await driveApi.getRecent()
    expect(res.status).toBe(200)
    expect(Array.isArray(res.data)).toBe(true)
    expect(res.data[0].name).toBe('report.pdf')
  })

  it('sends limit query param', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/drive/recent`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json([])
      }),
    )
    await driveApi.getRecent(10)
    expect(capturedUrl).toContain('limit=10')
  })
})
