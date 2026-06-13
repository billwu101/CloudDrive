import { useEffect, useState } from 'react'

import { authApi } from '@/api/authApi'
import { useAuthStore } from '@/stores/authStore'

/**
 * Attempts a silent token refresh on startup so users aren't redirected
 * to /login after a page reload while their refresh token cookie is still valid.
 *
 * Renders nothing until the attempt settles (success or failure), preventing
 * RequireAuth from redirecting before we know the user's actual auth state.
 */
export function AuthInitializer({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)
  const setToken = useAuthStore((s) => s.setToken)

  useEffect(() => {
    authApi
      .refresh()
      .then((res) => setToken(res.data.access_token))
      .catch(() => {})
      .finally(() => setReady(true))
  }, [setToken])

  if (!ready) return null

  return <>{children}</>
}
