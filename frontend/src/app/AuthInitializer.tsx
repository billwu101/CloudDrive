import { useEffect, useState } from 'react'

import { refreshAccessToken } from '@/api/client'

/**
 * Attempts a silent token refresh on startup so users aren't redirected
 * to /login after a page reload while their refresh token cookie is still valid.
 *
 * Renders nothing until the attempt settles (success or failure), preventing
 * RequireAuth from redirecting before we know the user's actual auth state.
 */
export function AuthInitializer({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let active = true

    void refreshAccessToken().finally(() => {
      if (active) setReady(true)
    })

    return () => {
      active = false
    }
  }, [])

  if (!ready) return null

  return <>{children}</>
}
