import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { ForgotPasswordPage } from './ForgotPasswordPage'

const BASE = 'http://localhost:8000/api/v1'

let lastRequestBody: { email: string } | null = null

const server = setupServer(
  http.post(`${BASE}/auth/forgot-password`, async ({ request }) => {
    lastRequestBody = (await request.json()) as { email: string }
    return HttpResponse.json({
      message: 'If an account exists for that email, a reset password has been sent.',
    })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  lastRequestBody = null
})
afterAll(() => server.close())

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ForgotPasswordPage', () => {
  it('renders the reset form', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /reset your password/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
  })

  it('validates the email field', async () => {
    renderPage()
    await userEvent.type(screen.getByLabelText(/email/i), 'notanemail')
    await userEvent.click(screen.getByRole('button', { name: /send reset password/i }))
    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument()
    })
  })

  it('submits the email and shows a non-enumerable confirmation', async () => {
    renderPage()
    await userEvent.type(screen.getByLabelText(/email/i), 'alice@example.com')
    await userEvent.click(screen.getByRole('button', { name: /send reset password/i }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/if an account exists/i)
    })
    expect(lastRequestBody).toEqual({ email: 'alice@example.com' })
    // Form is replaced by the confirmation — no submit button remains.
    expect(screen.queryByRole('button', { name: /send reset password/i })).not.toBeInTheDocument()
  })
})
