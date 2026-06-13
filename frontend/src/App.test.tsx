import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import App from './App'

afterEach(() => {
  cleanup()
  useAuthStore.setState({ accessToken: null, user: null })
})

describe('App routing', () => {
  // AuthInitializer attempts POST /auth/refresh on mount before rendering the
  // router. The MSW default handler returns 401, so we must wait for the
  // refresh to settle before the login page becomes visible.
  it('redirects unauthenticated users to /login', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
    })
  })
})
