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

  it('prevents native selection for UI text but allows editable controls', () => {
    render(<App />)

    const label = document.createElement('span')
    label.textContent = 'Sidebar label'
    document.body.appendChild(label)

    const labelSelection = new Event('selectstart', {
      bubbles: true,
      cancelable: true,
    })
    label.dispatchEvent(labelSelection)
    expect(labelSelection.defaultPrevented).toBe(true)

    const input = document.createElement('input')
    document.body.appendChild(input)

    const inputSelection = new Event('selectstart', {
      bubbles: true,
      cancelable: true,
    })
    input.dispatchEvent(inputSelection)
    expect(inputSelection.defaultPrevented).toBe(false)

    label.remove()
    input.remove()
  })
})
