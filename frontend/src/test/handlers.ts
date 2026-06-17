/**
 * Shared MSW request handlers for integration tests.
 * Individual unit test files may add/override handlers via server.use().
 */
import { http, HttpResponse } from 'msw'

const BASE = 'http://localhost:8000/api/v1'

// ── Fixtures ──────────────────────────────────────────────────────────────────

export const MOCK_USER = {
  id: 'user-1',
  email: 'alice@example.com',
  username: 'alice',
  avatar_url: null,
  quota_bytes: 15 * 1024 * 1024 * 1024,
  used_bytes: 1024 * 1024,
  is_active: true,
  is_admin: false,
  must_change_password: false,
  created_at: '2024-01-01T00:00:00Z',
}

export const MOCK_QUOTA = {
  quota_bytes: 15 * 1024 * 1024 * 1024,
  used_bytes: 1024 * 1024,
  available_bytes: 15 * 1024 * 1024 * 1024 - 1024 * 1024,
  used_percent: 0.007,
}

export const MOCK_FOLDER = {
  id: 'folder-1',
  owner_id: 'user-1',
  parent_id: null,
  item_type: 'FOLDER' as const,
  name: 'My Folder',
  mime_type: null,
  extension: null,
  size_bytes: 0,
  is_starred: false,
  is_deleted: false,
  deleted_at: null,
  created_by: 'user-1',
  updated_by: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

export const MOCK_FILE = {
  id: 'file-1',
  owner_id: 'user-1',
  parent_id: null,
  item_type: 'FILE' as const,
  name: 'report.txt',
  mime_type: 'text/plain',
  extension: 'txt',
  size_bytes: 1024,
  is_starred: false,
  is_deleted: false,
  deleted_at: null,
  created_by: 'user-1',
  updated_by: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

export const MOCK_ASSISTANT_SKILL = {
  id: 'skill-1',
  name: 'inspect_item_details',
  description: 'Show details for a selected drive item.',
  manifest: {
    name: 'inspect_item_details',
    description: 'Show details for a selected drive item.',
    version: '1.0.0',
    ui: {
      context_menu: [
        {
          label: 'Inspect details',
          handler: 'inspect_item_details',
          item_types: ['FILE', 'FOLDER'],
        },
      ],
    },
  },
  code: 'handler: inspect_item_details',
  status: 'installed',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

// ── Auth handlers ─────────────────────────────────────────────────────────────

const authHandlers = [
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    const body = await request.json() as { email: string; password: string }
    if (body.email === 'alice@example.com' && body.password === 'Password123!') {
      return HttpResponse.json({ access_token: 'mock-access-token', token_type: 'bearer' })
    }
    return HttpResponse.json({ code: 'UNAUTHORIZED', message: 'Invalid credentials' }, { status: 401 })
  }),

  http.post(`${BASE}/auth/register`, async ({ request }) => {
    const body = await request.json() as { email: string; username: string; password: string }
    return HttpResponse.json(
      { ...MOCK_USER, email: body.email, username: body.username },
      { status: 201 },
    )
  }),

  http.post(`${BASE}/auth/logout`, () => new HttpResponse(null, { status: 204 })),

  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),

  http.get(`${BASE}/auth/me`, () => HttpResponse.json(MOCK_USER)),
]

// ── User / Quota handlers ─────────────────────────────────────────────────────

const userHandlers = [
  http.get(`${BASE}/users/me`, () => HttpResponse.json(MOCK_USER)),
  http.get(`${BASE}/users/me/quota`, () => HttpResponse.json(MOCK_QUOTA)),
]

// ── Drive handlers ────────────────────────────────────────────────────────────

const driveHandlers = [
  http.get(`${BASE}/drive/items`, () =>
    HttpResponse.json({
      items: [MOCK_FOLDER, MOCK_FILE],
      total: 2,
      page: 1,
      page_size: 20,
      pages: 1,
    }),
  ),

  http.post(`${BASE}/drive/folders`, async ({ request }) => {
    const body = await request.json() as { name: string; parent_id?: string }
    return HttpResponse.json(
      { ...MOCK_FOLDER, id: `folder-${Date.now()}`, name: body.name },
      { status: 201 },
    )
  }),

  http.patch(`${BASE}/drive/items/:id/name`, async ({ params, request }) => {
    const body = await request.json() as { name: string }
    return HttpResponse.json({ ...MOCK_FOLDER, id: params.id as string, name: body.name })
  }),

  http.patch(`${BASE}/drive/items/:id/parent`, async ({ params, request }) => {
    const body = await request.json() as { parent_id: string | null }
    return HttpResponse.json({ ...MOCK_FOLDER, id: params.id as string, parent_id: body.parent_id })
  }),

  http.put(`${BASE}/drive/items/:id/star`, async ({ params, request }) => {
    const body = await request.json() as { is_starred: boolean }
    return HttpResponse.json({ ...MOCK_FOLDER, id: params.id as string, is_starred: body.is_starred })
  }),
]

// ── Upload handler ────────────────────────────────────────────────────────────

const uploadHandlers = [
  http.post(`${BASE}/upload/simple`, () =>
    HttpResponse.json(
      { ...MOCK_FILE, id: `file-${Date.now()}` },
      { status: 201 },
    ),
  ),
]

// ── Trash handlers ────────────────────────────────────────────────────────────

const trashHandlers = [
  http.get(`${BASE}/trash`, () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50, pages: 1 }),
  ),

  http.post(`${BASE}/trash/items/:id`, ({ params }) =>
    HttpResponse.json({ ...MOCK_FOLDER, id: params.id as string, is_deleted: true }),
  ),

  http.post(`${BASE}/trash/items/:id/restore`, ({ params }) =>
    HttpResponse.json({ ...MOCK_FOLDER, id: params.id as string, is_deleted: false }),
  ),

  http.delete(`${BASE}/trash/items/:id`, () => new HttpResponse(null, { status: 204 })),
  http.delete(`${BASE}/trash`, () => new HttpResponse(null, { status: 204 })),
]

// ── Search handlers ───────────────────────────────────────────────────────────

const searchHandlers = [
  http.get(`${BASE}/search`, ({ request }) => {
    const url = new URL(request.url)
    const q = url.searchParams.get('q') ?? ''
    const items = q ? [MOCK_FILE] : []
    return HttpResponse.json({ items, total: items.length, page: 1, page_size: 20, pages: 1 })
  }),
]

// ── Share handlers ────────────────────────────────────────────────────────────

const shareHandlers = [
  http.get(`${BASE}/share/shared-with-me`, () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 20, pages: 1 }),
  ),

  http.post(`${BASE}/share/items/:id`, async ({ params, request }) => {
    const body = await request.json() as { target_email: string; permission: string }
    return HttpResponse.json(
      {
        id: 'share-1',
        item_id: params.id,
        owner_id: 'user-1',
        target_user_id: 'user-2',
        permission: body.permission,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
      { status: 201 },
    )
  }),

  http.delete(`${BASE}/share/items/:id/users/:userId`, () =>
    new HttpResponse(null, { status: 204 }),
  ),

  http.post(`${BASE}/share/items/:id/links`, async ({ params, request }) => {
    const body = await request.json() as { permission: string }
    return HttpResponse.json(
      {
        id: 'link-1',
        item_id: params.id,
        token: 'public-token-abc',
        permission: body.permission,
        expires_at: null,
        is_active: true,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
      },
      { status: 201 },
    )
  }),
]

// ── Recent / Starred handlers ─────────────────────────────────────────────────

const activityHandlers = [
  http.get(`${BASE}/drive/recent`, () => HttpResponse.json([])),
]

// ── Assistant handlers ───────────────────────────────────────────────────────

const assistantHandlers = [
  http.post(`${BASE}/assistant/chat`, async ({ request }) => {
    const body = await request.json() as { message: string; session_id?: string }
    const wantsContextMenu = /right[- ]click|context menu|右鍵/i.test(body.message)
    return HttpResponse.json({
      session_id: body.session_id ?? 'assistant-session-1',
      message: wantsContextMenu
        ? 'I drafted a right-click menu skill.'
        : `Assistant heard: ${body.message}`,
      tool_calls: [],
      tool_results: [],
      skill_proposal: wantsContextMenu ? { ...MOCK_ASSISTANT_SKILL, status: 'pending' } : null,
    })
  }),

  http.get(`${BASE}/assistant/skills`, () => HttpResponse.json([])),

  http.get(`${BASE}/assistant/workflows/saved`, () => HttpResponse.json([])),

  http.post(`${BASE}/assistant/workflows/save`, async ({ request }) => {
    const body = (await request.json()) as { name: string; source_nl?: string; steps: unknown[] }
    return HttpResponse.json({
      id: 'saved-workflow-1',
      name: body.name,
      source_nl: body.source_nl ?? '',
      steps: [],
      created_at: '2024-01-01T00:00:00Z',
    })
  }),

  http.post(`${BASE}/assistant/workflows/saved/:id/rerun`, ({ params }) =>
    HttpResponse.json({
      workflow_id: params.id,
      status: 'executed',
      message: 'Saved workflow executed.',
      results: [],
    }),
  ),

  http.post(`${BASE}/assistant/skills/:id/approve`, ({ params }) =>
    HttpResponse.json({
      skill: { ...MOCK_ASSISTANT_SKILL, id: params.id as string, status: 'installed' },
      message: 'inspect_item_details installed.',
    }),
  ),

  http.post(`${BASE}/assistant/skills/:id/execute`, async ({ params, request }) => {
    const body = await request.json() as { item_id: string }
    return HttpResponse.json({
      skill_id: params.id,
      skill_name: 'inspect_item_details',
      item_id: body.item_id,
      message: `Details for ${MOCK_FILE.name}`,
      output: {
        name: MOCK_FILE.name,
        item_type: MOCK_FILE.item_type,
        size_bytes: MOCK_FILE.size_bytes,
      },
    })
  }),
]

// ── Export all ────────────────────────────────────────────────────────────────

export const handlers = [
  ...authHandlers,
  ...userHandlers,
  ...driveHandlers,
  ...uploadHandlers,
  ...trashHandlers,
  ...searchHandlers,
  ...shareHandlers,
  ...activityHandlers,
  ...assistantHandlers,
]
