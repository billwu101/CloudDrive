import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'
import { AssistantPanel } from './AssistantPanel'

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
  status: 'pending',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const server = setupServer(
  http.post(`${BASE}/assistant/chat`, async ({ request }) => {
    const body = await request.json() as { message: string; session_id?: string }
    return HttpResponse.json({
      session_id: body.session_id ?? 'session-1',
      message: `Done: ${body.message}`,
      tool_calls: [],
      tool_results: [],
    })
  }),
  http.post(`${BASE}/assistant/skills/:id/approve`, ({ params }) =>
    HttpResponse.json({
      skill: { ...mockSkill, id: params.id as string, status: 'installed' },
      message: 'inspect_item_details installed.',
    }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
  useAuthStore.setState({ accessToken: 'test-token' })
})
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
})
afterAll(() => server.close())

function renderAssistantPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AssistantPanel />
    </QueryClientProvider>,
  )
}

describe('AssistantPanel', () => {
  it('opens inside the app shell and sends a chat message', async () => {
    renderAssistantPanel()

    await userEvent.click(screen.getByRole('button', { name: /open assistant/i }))
    expect(screen.getByRole('region', { name: /clouddrive assistant/i })).toBeInTheDocument()

    const input = screen.getByLabelText(/assistant message/i)
    await userEvent.type(input, 'hello')
    await userEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByText('Done: hello')).toBeInTheDocument()
    })
  })

  it('renders backend errors as assistant messages', async () => {
    server.use(
      http.post(`${BASE}/assistant/chat`, () =>
        HttpResponse.json(
          { error: { code: 'ASSISTANT_UNAVAILABLE', message: 'Assistant unavailable', details: {} } },
          { status: 503 },
        ),
      ),
    )
    renderAssistantPanel()

    await userEvent.click(screen.getByRole('button', { name: /open assistant/i }))
    await userEvent.type(screen.getByLabelText(/assistant message/i), 'hello')
    await userEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByText('Assistant is unavailable right now.')).toBeInTheDocument()
    })
  })

  it('renders and approves a generated skill proposal', async () => {
    server.use(
      http.post(`${BASE}/assistant/chat`, async ({ request }) => {
        const body = await request.json() as { session_id?: string }
        return HttpResponse.json({
          session_id: body.session_id ?? 'session-1',
          message: 'I drafted a right-click menu skill.',
          tool_calls: [],
          tool_results: [],
          skill_proposal: mockSkill,
        })
      }),
    )
    renderAssistantPanel()

    await userEvent.click(screen.getByRole('button', { name: /open assistant/i }))
    await userEvent.type(
      screen.getByLabelText(/assistant message/i),
      'create a right click inspect details action',
    )
    await userEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByText('Skill proposal')).toBeInTheDocument()
    })
    expect(screen.getByText(/adds "inspect details" to file, folder/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /approve/i }))

    await waitFor(() => {
      expect(screen.getByText('Installed Inspect details.')).toBeInTheDocument()
    })
  })

  it('renders step results (storage quota) in the assistant bubble', async () => {
    server.use(
      http.post(`${BASE}/assistant/chat`, async ({ request }) => {
        const body = (await request.json()) as { session_id?: string }
        return HttpResponse.json({
          session_id: body.session_id ?? 'session-1',
          message: 'I will check your current storage usage.',
          tool_calls: [],
          tool_results: [],
          plan: { workflow_id: null, status: 'auto_executed', steps: [] },
          results: [
            {
              index: 0,
              skill: 'storage_quota',
              ok: true,
              output: {
                quota_bytes: 16106127360,
                used_bytes: 0,
                available_bytes: 16106127360,
                used_percent: 0,
              },
            },
          ],
        })
      }),
    )
    renderAssistantPanel()

    await userEvent.click(screen.getByRole('button', { name: /open assistant/i }))
    await userEvent.type(screen.getByLabelText(/assistant message/i), 'how much space left')
    await userEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByText(/15\.0 GB free of 15\.0 GB \(0% used\)/i)).toBeInTheDocument()
    })
    expect(screen.getByText('storage_quota')).toBeInTheDocument()
  })

  it('lists file names from a list_items result', async () => {
    server.use(
      http.post(`${BASE}/assistant/chat`, async ({ request }) => {
        const body = (await request.json()) as { session_id?: string }
        return HttpResponse.json({
          session_id: body.session_id ?? 'session-1',
          message: 'Listing your root files.',
          tool_calls: [],
          tool_results: [],
          plan: { workflow_id: null, status: 'auto_executed', steps: [] },
          results: [
            {
              index: 0,
              skill: 'list_items',
              ok: true,
              output: {
                total: 3,
                items: [
                  { name: 'test' },
                  { name: 'IMG_0001.pdf' },
                  { name: 'IMG_3447.mov' },
                ],
              },
            },
          ],
        })
      }),
    )
    renderAssistantPanel()

    await userEvent.click(screen.getByRole('button', { name: /open assistant/i }))
    await userEvent.type(screen.getByLabelText(/assistant message/i), 'list file names')
    await userEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/3 items: test, IMG_0001\.pdf, IMG_3447\.mov/i),
      ).toBeInTheDocument()
    })
  })

  it('shows a pending workflow plan and runs it on confirm', async () => {
    server.use(
      http.post(`${BASE}/assistant/chat`, async ({ request }) => {
        const body = (await request.json()) as { session_id?: string }
        return HttpResponse.json({
          session_id: body.session_id ?? 'session-1',
          message: 'I will move it.',
          tool_calls: [],
          tool_results: [],
          results: [],
          plan: {
            workflow_id: 'wf-1',
            status: 'pending_approval',
            steps: [
              {
                index: 0,
                skill: 'trash_item',
                arguments: {},
                depends_on: [],
                permission_tier: 'destructive',
                requires_approval: true,
              },
            ],
          },
        })
      }),
      http.post(`${BASE}/assistant/workflows/:id/confirm`, ({ params }) =>
        HttpResponse.json({
          workflow_id: params.id as string,
          status: 'executed',
          message: 'Workflow executed.',
          results: [{ index: 0, skill: 'trash_item', ok: true }],
        }),
      ),
    )
    renderAssistantPanel()

    await userEvent.click(screen.getByRole('button', { name: /open assistant/i }))
    await userEvent.type(screen.getByLabelText(/assistant message/i), 'delete the file')
    await userEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByText(/plan needs your confirmation/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/1\. trash_item/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /confirm & run/i }))

    await waitFor(() => {
      expect(screen.getByText('Done — the plan ran successfully.')).toBeInTheDocument()
    })
    expect(screen.queryByText(/plan needs your confirmation/i)).not.toBeInTheDocument()
  })

  it('cancels a pending workflow plan', async () => {
    server.use(
      http.post(`${BASE}/assistant/chat`, async ({ request }) => {
        const body = (await request.json()) as { session_id?: string }
        return HttpResponse.json({
          session_id: body.session_id ?? 'session-1',
          message: 'I will move it.',
          tool_calls: [],
          tool_results: [],
          results: [],
          plan: {
            workflow_id: 'wf-1',
            status: 'pending_approval',
            steps: [
              {
                index: 0,
                skill: 'trash_item',
                arguments: {},
                depends_on: [],
                permission_tier: 'destructive',
                requires_approval: true,
              },
            ],
          },
        })
      }),
      http.post(`${BASE}/assistant/workflows/:id/cancel`, ({ params }) =>
        HttpResponse.json({
          workflow_id: params.id as string,
          status: 'cancelled',
          message: 'Workflow cancelled.',
          results: [],
        }),
      ),
    )
    renderAssistantPanel()

    await userEvent.click(screen.getByRole('button', { name: /open assistant/i }))
    await userEvent.type(screen.getByLabelText(/assistant message/i), 'delete the file')
    await userEvent.click(screen.getByRole('button', { name: /send message/i }))

    await waitFor(() => {
      expect(screen.getByText(/plan needs your confirmation/i)).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))

    await waitFor(() => {
      expect(screen.getByText('Cancelled. Nothing was changed.')).toBeInTheDocument()
    })
  })
})
