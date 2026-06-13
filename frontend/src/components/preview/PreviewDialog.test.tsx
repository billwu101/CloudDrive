import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { PreviewDialog } from './PreviewDialog'

const BASE = 'http://localhost:8000/api/v1'

const server = setupServer(
  http.get(`${BASE}/preview/:id/info`, ({ params }) => {
    const id = params.id as string
    if (id === 'img-1') {
      return HttpResponse.json({
        item_id: 'img-1',
        preview_type: 'image',
        mime_type: 'image/png',
        size_bytes: 1024,
        filename: 'photo.png',
      })
    }
    if (id === 'pdf-1') {
      return HttpResponse.json({
        item_id: 'pdf-1',
        preview_type: 'pdf',
        mime_type: 'application/pdf',
        size_bytes: 2048,
        filename: 'doc.pdf',
      })
    }
    if (id === 'txt-1') {
      return HttpResponse.json({
        item_id: 'txt-1',
        preview_type: 'text',
        mime_type: 'text/plain',
        size_bytes: 256,
        filename: 'readme.txt',
      })
    }
    if (id === 'unsup-1') {
      return HttpResponse.json({
        item_id: 'unsup-1',
        preview_type: 'unsupported',
        mime_type: 'application/octet-stream',
        size_bytes: 512,
        filename: 'archive.bin',
      })
    }
    return HttpResponse.json({ code: 'NOT_FOUND' }, { status: 404 })
  }),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: 'tok' })
})
afterAll(() => server.close())

function renderDialog(itemId: string | null, onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <PreviewDialog itemId={itemId} onClose={onClose} />
    </QueryClientProvider>,
  )
}

describe('PreviewDialog', () => {
  it('renders nothing when itemId is null', () => {
    const { container } = renderDialog(null)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows loading spinner initially', () => {
    useAuthStore.setState({ accessToken: 'tok' })
    renderDialog('img-1')
    expect(screen.getByLabelText('Loading preview')).toBeInTheDocument()
  })

  it('renders image preview', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    renderDialog('img-1')
    await waitFor(() => expect(screen.getByRole('img', { name: 'photo.png' })).toBeInTheDocument())
  })

  it('renders unsupported preview with download link', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    renderDialog('unsup-1')
    await waitFor(() =>
      expect(screen.getByText('Preview not available for this file type.')).toBeInTheDocument(),
    )
    expect(screen.getAllByRole('link', { name: /download/i }).length).toBeGreaterThan(0)
  })

  it('calls onClose when Escape is pressed', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    const onClose = vi.fn()
    renderDialog('img-1', onClose)
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when close button is clicked', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    const onClose = vi.fn()
    renderDialog('img-1', onClose)
    await userEvent.click(screen.getByRole('button', { name: /close preview/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('shows error state when API fails', async () => {
    useAuthStore.setState({ accessToken: 'tok' })
    server.use(
      http.get(`${BASE}/preview/:id/info`, () =>
        HttpResponse.json({ code: 'SERVER_ERROR' }, { status: 500 }),
      ),
    )
    renderDialog('img-1')
    await waitFor(() =>
      expect(screen.getByText('Failed to load preview.')).toBeInTheDocument(),
    )
  })
})
