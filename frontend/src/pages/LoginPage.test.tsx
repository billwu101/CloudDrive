import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { LoginPage } from './LoginPage'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const BASE = 'http://localhost:8000/api/v1'

const server = setupServer(
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    const body = await request.json() as { email: string; password: string }
    if (body.email === 'user@test.com' && body.password === 'correct') {
      return HttpResponse.json({ access_token: 'tok', token_type: 'bearer' })
    }
    return HttpResponse.json({ code: 'INVALID_CREDENTIALS', message: 'Invalid credentials' }, { status: 401 })
  }),
  http.get(`${BASE}/users/me`, () =>
    HttpResponse.json({ id: 'u1', email: 'user@test.com', username: 'user', quota_bytes: 0, used_bytes: 0 }),
  ),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
  mockNavigate.mockReset()
})
afterAll(() => server.close())

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LoginPage', () => {
  it('renders sign in form', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('shows validation errors when form is submitted empty', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument()
    })
  })

  it('shows validation error for invalid email', async () => {
    renderPage()
    await userEvent.type(screen.getByLabelText(/email/i), 'notanemail')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument()
    })
  })

  it('sets token in store and navigates to /drive on success', async () => {
    renderPage()
    await userEvent.type(screen.getByLabelText(/email/i), 'user@test.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'correct')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => {
      expect(useAuthStore.getState().accessToken).toBe('tok')
      expect(mockNavigate).toHaveBeenCalledWith('/drive')
    })
  })

  it('shows error message on wrong credentials', async () => {
    renderPage()
    await userEvent.type(screen.getByLabelText(/email/i), 'user@test.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/invalid credentials/i)
    })
  })
})
