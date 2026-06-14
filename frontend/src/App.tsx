import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect } from 'react'
import { RouterProvider } from 'react-router-dom'

import { AuthInitializer } from './app/AuthInitializer'
import { router } from './app/router'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
    mutations: { retry: 0 },
  },
})

export default function App() {
  useEffect(() => {
    const preventTextSelection = (event: Event) => {
      const target = event.target
      const element =
        target instanceof Element
          ? target
          : target instanceof Node
            ? target.parentElement
            : null

      if (element?.closest('input, textarea, [contenteditable="true"]')) return

      event.preventDefault()
      window.getSelection()?.removeAllRanges()
    }

    document.addEventListener('selectstart', preventTextSelection)
    return () => document.removeEventListener('selectstart', preventTextSelection)
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
      <AuthInitializer>
        <RouterProvider router={router} />
      </AuthInitializer>
    </QueryClientProvider>
  )
}
