import { render, screen } from '@testing-library/react'
import { cleanup } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import App from './App'

afterEach(() => {
  cleanup()
  useAuthStore.setState({ accessToken: null, user: null })
})

describe('App routing', () => {
  it('redirects unauthenticated users to /login', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
  })
})
