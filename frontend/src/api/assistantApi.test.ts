import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { assistantApi } from './assistantApi'

const BASE = 'http://localhost:8000/api/v1'

const mockSkill = {
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
  http.get(`${BASE}/assistant/skills`, ({ request }) => {
    const url = new URL(request.url)
    expect(url.searchParams.get('status')).toBe('installed')
    return HttpResponse.json([mockSkill])
  }),
  http.post(`${BASE}/assistant/skills/:id/approve`, ({ params }) =>
    HttpResponse.json({
      skill: { ...mockSkill, id: params.id as string, status: 'installed' },
      message: 'inspect_item_details installed.',
    }),
  ),
  http.post(`${BASE}/assistant/skills/:id/execute`, async ({ params, request }) => {
    const body = await request.json() as { item_id: string }
    return HttpResponse.json({
      skill_id: params.id,
      skill_name: 'inspect_item_details',
      item_id: body.item_id,
      message: 'Details for report.txt',
      output: { name: 'report.txt', item_type: 'FILE' },
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

  it('lists, approves, and executes assistant skills', async () => {
    const skills = await assistantApi.listSkills()
    const approval = await assistantApi.approveSkill('skill-1')
    const execution = await assistantApi.executeSkill('skill-1', { item_id: 'file-1' })

    expect(skills.data).toHaveLength(1)
    expect(skills.data[0].manifest.ui.context_menu[0].label).toBe('Inspect details')
    expect(approval.data.skill.status).toBe('installed')
    expect(execution.data.output.name).toBe('report.txt')
  })
})
