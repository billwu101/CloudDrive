import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { SettingsPage } from './SettingsPage'

const BASE = 'http://localhost:8000/api/v1'

const MOCK_USER = {
  id: 'user-1',
  email: 'alice@example.com',
  username: 'alice',
  avatar_url: null,
  quota_bytes: 1024,
  used_bytes: 128,
  is_active: true,
  is_admin: false,
  created_at: '2024-01-01T00:00:00Z',
}

const server = setupServer(
  http.get(`${BASE}/users/me`, () => HttpResponse.json(MOCK_USER)),
  http.patch(`${BASE}/users/me`, async ({ request }) => {
    const body = await request.json() as { username: string }
    return HttpResponse.json({ ...MOCK_USER, username: body.username })
  }),
  http.patch(`${BASE}/users/me/email`, async ({ request }) => {
    const body = await request.json() as { email: string }
    if (body.email === 'taken@example.com') {
      return HttpResponse.json(
        {
          error: {
            code: 'EMAIL_ALREADY_EXISTS',
            message: 'Email already in use',
            details: {},
          },
        },
        { status: 409 },
      )
    }
    return HttpResponse.json({ ...MOCK_USER, email: body.email })
  }),
  http.patch(`${BASE}/users/me/password`, async ({ request }) => {
    const body = await request.json() as {
      current_password: string
      new_password: string
    }
    if (body.current_password !== 'current-password') {
      return HttpResponse.json(
        {
          error: {
            code: 'INVALID_CREDENTIALS',
            message: 'Current password is incorrect',
            details: {},
          },
        },
        { status: 400 },
      )
    }
    return new HttpResponse(null, { status: 204 })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
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
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>,
  )
}

describe('SettingsPage', () => {
  it('loads the current profile into the forms', async () => {
    renderPage()
    expect(screen.getByText(/loading account settings/i)).toBeInTheDocument()
    expect(await screen.findByLabelText('Username')).toHaveValue('alice')
    expect(screen.getByLabelText('Email address')).toHaveValue('alice@example.com')
  })

  it('updates the username and synchronizes the auth store', async () => {
    const user = userEvent.setup()
    renderPage()

    const usernameInput = await screen.findByLabelText('Username')
    await user.clear(usernameInput)
    await user.type(usernameInput, 'alice-updated')
    await user.click(screen.getByRole('button', { name: 'Save username' }))

    expect(await screen.findByText('Username updated.')).toBeInTheDocument()
    expect(useAuthStore.getState().user?.username).toBe('alice-updated')
    expect(screen.getByRole('button', { name: 'Save username' })).toBeDisabled()
  })

  it('shows the backend message when an email is already used', async () => {
    const user = userEvent.setup()
    renderPage()

    const emailInput = await screen.findByLabelText('Email address')
    await user.clear(emailInput)
    await user.type(emailInput, 'taken@example.com')
    await user.click(screen.getByRole('button', { name: 'Save email' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Email already in use')
  })

  it('validates matching passwords and changes the password', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByLabelText('Username')

    await user.type(screen.getByLabelText('Current password'), 'current-password')
    await user.type(screen.getByLabelText('New password'), 'new-password')
    await user.type(screen.getByLabelText('Confirm new password'), 'different-password')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Confirm new password'))
    await user.type(screen.getByLabelText('Confirm new password'), 'new-password')
    await user.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByText('Password changed successfully.')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByLabelText('Current password')).toHaveValue('')
      expect(screen.getByLabelText('New password')).toHaveValue('')
    })
  })
})
