/**
 * Tests for previewApi — proposal.md §5.1 功能 15
 *
 * 覆蓋功能：
 *   - 取得預覽資訊 (GET /preview/:id/info)
 *   - 請求取消 (AbortSignal)
 *   - 取得下載 URL (getContentUrl)
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { getContentUrl, previewApi } from './previewApi'

const BASE = 'http://localhost:8000/api/v1'

const MOCK_PREVIEW_INFO = {
  id: 'file-1',
  name: 'photo.jpg',
  mime_type: 'image/jpeg',
  size_bytes: 204800,
  preview_url: `${BASE}/preview/file-1/content`,
  download_url: `${BASE}/download/file-1`,
}

const server = setupServer(
  http.get(`${BASE}/preview/:id/info`, ({ params }) => {
    if (params.id === 'no-access') {
      return HttpResponse.json(
        { code: 'FORBIDDEN', message: 'Access denied' },
        { status: 403 },
      )
    }
    if (params.id === 'not-found') {
      return HttpResponse.json(
        { code: 'NOT_FOUND', message: 'Item not found' },
        { status: 404 },
      )
    }
    return HttpResponse.json({ ...MOCK_PREVIEW_INFO, id: params.id as string })
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

// ── 取得預覽資訊 ──────────────────────────────────────────────────────────────

describe('getInfo (GET /preview/:id/info)', () => {
  it('returns preview metadata for a file', async () => {
    const res = await previewApi.getInfo('file-1')
    expect(res.status).toBe(200)
    expect(res.data.id).toBe('file-1')
    expect(res.data.mime_type).toBe('image/jpeg')
  })

  it('response includes name and size_bytes', async () => {
    const res = await previewApi.getInfo('file-1')
    expect(res.data.name).toBe('photo.jpg')
    expect(res.data.size_bytes).toBeGreaterThan(0)
  })

  it('calls the correct URL path /preview/:id/info', async () => {
    let capturedUrl = ''
    server.use(
      http.get(`${BASE}/preview/:id/info`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json(MOCK_PREVIEW_INFO)
      }),
    )
    await previewApi.getInfo('file-42')
    expect(capturedUrl).toContain('/preview/file-42/info')
  })

  it('rejects with 403 when user has no access', async () => {
    await expect(
      previewApi.getInfo('no-access'),
    ).rejects.toMatchObject({ status: 403 })
  })

  it('rejects with 404 when item does not exist', async () => {
    await expect(
      previewApi.getInfo('not-found'),
    ).rejects.toMatchObject({ status: 404 })
  })
})

// ── 請求取消 ──────────────────────────────────────────────────────────────────

describe('getInfo with AbortSignal', () => {
  it('cancels the request when signal is aborted', async () => {
    const controller = new AbortController()
    server.use(
      http.get(`${BASE}/preview/:id/info`, async () => {
        await new Promise((r) => setTimeout(r, 500))
        return HttpResponse.json(MOCK_PREVIEW_INFO)
      }),
    )
    const promise = previewApi.getInfo('file-1', controller.signal)
    controller.abort()
    await expect(promise).rejects.toMatchObject({ code: 'CANCELED' })
  })
})

// ── 取得下載 URL ──────────────────────────────────────────────────────────────

describe('getContentUrl', () => {
  it('returns URL ending in /download/:id', () => {
    const url = getContentUrl('file-1')
    expect(url).toContain('/download/file-1')
  })

  it('returns a string (not a promise)', () => {
    const url = getContentUrl('file-1')
    expect(typeof url).toBe('string')
  })

  it('embeds the correct item ID in the URL', () => {
    const url = getContentUrl('abc-123-xyz')
    expect(url).toContain('abc-123-xyz')
  })

  it('URL is based on the configured API base URL', () => {
    const url = getContentUrl('file-1')
    expect(url).toMatch(/^https?:\/\//)
  })
})
