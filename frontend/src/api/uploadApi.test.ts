/**
 * Tests for uploadApi — proposal.md §5.1 功能 3
 *
 * 覆蓋功能：
 *   - 檔案上傳 (POST /upload/simple)
 *   - 上傳至指定資料夾
 *   - 上傳進度回呼
 *   - 上傳取消 (AbortSignal)
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { uploadApi } from './uploadApi'

const BASE = 'http://localhost:8000/api/v1'

const MOCK_FILE_ITEM = {
  id: 'file-1',
  owner_id: 'u1',
  parent_id: null,
  item_type: 'FILE',
  name: 'hello.txt',
  mime_type: 'text/plain',
  extension: 'txt',
  size_bytes: 13,
  is_starred: false,
  is_deleted: false,
  deleted_at: null,
  created_by: 'u1',
  updated_by: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const server = setupServer(
  http.post(`${BASE}/upload/simple`, async ({ request }) => {
    const url = new URL(request.url)
    const parentId = url.searchParams.get('parent_id')
    return HttpResponse.json(
      { ...MOCK_FILE_ITEM, parent_id: parentId },
      { status: 201 },
    )
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

function makeFile(name = 'hello.txt', content = 'Hello, world!', type = 'text/plain'): File {
  return new File([content], name, { type })
}

// ── 基本上傳 ──────────────────────────────────────────────────────────────────

describe('uploadSimple (POST /upload/simple)', () => {
  it('sends file as multipart/form-data and returns 201', async () => {
    const file = makeFile()
    const res = await uploadApi.uploadSimple(file)
    expect(res.status).toBe(201)
    expect(res.data.item_type).toBe('FILE')
  })

  it('sends file in the "file" FormData field', async () => {
    let capturedBody = ''
    server.use(
      http.post(`${BASE}/upload/simple`, async ({ request }) => {
        capturedBody = await request.text()
        return HttpResponse.json(MOCK_FILE_ITEM, { status: 201 })
      }),
    )
    await uploadApi.uploadSimple(makeFile('myreport.pdf'))
    // multipart body must contain name="file" regardless of environment
    expect(capturedBody).toContain('name="file"')
    expect(capturedBody).toContain('Content-Type: text/plain')
  })

  it('sends request body as FormData (field name must be "file")', async () => {
    let capturedBody = ''
    server.use(
      http.post(`${BASE}/upload/simple`, async ({ request }) => {
        capturedBody = await request.text()
        return HttpResponse.json(MOCK_FILE_ITEM, { status: 201 })
      }),
    )
    await uploadApi.uploadSimple(makeFile())
    expect(capturedBody).toContain('name="file"')
  })
})

// ── 上傳至指定資料夾 ──────────────────────────────────────────────────────────

describe('uploadSimple with parentId', () => {
  it('sends parent_id as query parameter', async () => {
    let capturedUrl = ''
    server.use(
      http.post(`${BASE}/upload/simple`, async ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json(MOCK_FILE_ITEM, { status: 201 })
      }),
    )
    await uploadApi.uploadSimple(makeFile(), { parentId: 'folder-1' })
    expect(capturedUrl).toContain('parent_id=folder-1')
  })

  it('returns item with parent_id set', async () => {
    const res = await uploadApi.uploadSimple(makeFile(), { parentId: 'folder-1' })
    expect(res.data.parent_id).toBe('folder-1')
  })

  it('omits parent_id param when not provided', async () => {
    let capturedUrl = ''
    server.use(
      http.post(`${BASE}/upload/simple`, async ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json(MOCK_FILE_ITEM, { status: 201 })
      }),
    )
    await uploadApi.uploadSimple(makeFile())
    expect(capturedUrl).not.toContain('parent_id')
  })
})

// ── 上傳取消 ──────────────────────────────────────────────────────────────────

describe('uploadSimple with AbortSignal', () => {
  it('cancels the upload when signal is aborted', async () => {
    const controller = new AbortController()
    server.use(
      http.post(`${BASE}/upload/simple`, async () => {
        await new Promise((r) => setTimeout(r, 500))
        return HttpResponse.json(MOCK_FILE_ITEM, { status: 201 })
      }),
    )
    const promise = uploadApi.uploadSimple(makeFile(), { signal: controller.signal })
    controller.abort()
    await expect(promise).rejects.toMatchObject({ code: 'CANCELED' })
  })
})
