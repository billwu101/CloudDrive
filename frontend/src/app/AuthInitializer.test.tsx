import { StrictMode } from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/authStore'

import { AuthInitializer } from './AuthInitializer'

const BASE = 'http://localhost:8000/api/v1'
const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
  useAuthStore.setState({ accessToken: null, user: null })
})
afterAll(() => server.close())

describe('AuthInitializer', () => {
  it('restores the access token once when StrictMode mounts effects twice', async () => {
    let refreshCount = 0
    server.use(
      http.post(`${BASE}/auth/refresh`, async () => {
        refreshCount += 1
        await new Promise((resolve) => setTimeout(resolve, 20))
        return HttpResponse.json({
          access_token: 'restored-access-token',
          token_type: 'bearer',
        })
      }),
    )

    render(
      <StrictMode>
        <AuthInitializer>
          <div>Protected content</div>
        </AuthInitializer>
      </StrictMode>,
    )

    expect(await screen.findByText('Protected content')).toBeInTheDocument()
    expect(useAuthStore.getState().accessToken).toBe('restored-access-token')
    expect(refreshCount).toBe(1)
  })

  it('continues without a token when the refresh cookie is absent or expired', async () => {
    server.use(
      http.post(`${BASE}/auth/refresh`, () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'Refresh token has expired' } },
          { status: 401 },
        ),
      ),
    )

    render(
      <AuthInitializer>
        <div>Public router</div>
      </AuthInitializer>,
    )

    expect(await screen.findByText('Public router')).toBeInTheDocument()
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})
