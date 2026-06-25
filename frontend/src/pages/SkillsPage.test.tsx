import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import type { AssistantSkillResponse } from '@/api/types'
import { useAuthStore } from '@/stores/authStore'

import { SkillsPage } from './SkillsPage'

const BASE = 'http://localhost:8000/api/v1'

function makeSkill(overrides: Partial<AssistantSkillResponse> = {}): AssistantSkillResponse {
  return {
    id: 'skill-1',
    name: 'extract_gzip',
    description: 'Extracts the contents of a .gz file.',
    manifest: {
      name: 'extract_gzip',
      description: 'Extracts the contents of a .gz file.',
      version: '1.0.0',
      ui: {
        context_menu: [{ label: 'Extract .gz', handler: 'extract_gzip', item_types: ['FILE'] }],
      },
    },
    code: "def run(input_path, output_dir, params):\n    return {'ok': True}\n",
    status: 'installed',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
    ...overrides,
  }
}

let skills: AssistantSkillResponse[] = []

const server = setupServer(
  http.get(`${BASE}/assistant/skills`, () => HttpResponse.json(skills)),
  http.patch(`${BASE}/assistant/skills/:id`, async ({ params, request }) => {
    const body = (await request.json()) as { description?: string; code?: string }
    const found = skills.find((s) => s.id === params.id)!
    const updated = { ...found, ...body }
    skills = skills.map((s) => (s.id === params.id ? updated : s))
    return HttpResponse.json(updated)
  }),
  http.delete(`${BASE}/assistant/skills/:id`, ({ params }) => {
    skills = skills.filter((s) => s.id !== params.id)
    return new HttpResponse(null, { status: 204 })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
  skills = [makeSkill()]
  useAuthStore.setState({ accessToken: 'test-token', user: null })
})
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
})
afterAll(() => server.close())

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <SkillsPage />
    </QueryClientProvider>,
  )
}

describe('SkillsPage', () => {
  it('shows the installed skill count and lists skills', async () => {
    renderPage()
    expect(await screen.findByText('1 skill installed. Edit or remove the ones you no longer need.')).toBeInTheDocument()
    expect(screen.getByText('extract_gzip')).toBeInTheDocument()
    expect(screen.getByText('Right-click: Extract .gz')).toBeInTheDocument()
  })

  it('shows an empty state when there are no skills', async () => {
    skills = []
    renderPage()
    expect(await screen.findByText('No installed skills')).toBeInTheDocument()
  })

  it('edits a skill description', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('extract_gzip')

    await user.click(screen.getByRole('button', { name: /edit extract_gzip/i }))
    const input = await screen.findByLabelText('Description')
    await user.clear(input)
    await user.type(input, 'Unpacks gzip archives.')
    await user.click(screen.getByRole('button', { name: /save changes/i }))

    expect(await screen.findByText('Unpacks gzip archives.')).toBeInTheDocument()
  })

  it('deletes a skill after confirmation', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('extract_gzip')

    await user.click(screen.getByRole('button', { name: /delete extract_gzip/i }))
    await user.click(screen.getByRole('button', { name: /^delete$/i }))

    await waitFor(() => expect(screen.getByText('No installed skills')).toBeInTheDocument())
  })
})
