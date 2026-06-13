import type { ReactNode } from 'react'

interface MainContentProps {
  children: ReactNode
}

export function MainContent({ children }: MainContentProps) {
  return (
    <main className="flex-1 overflow-auto bg-background p-4">
      {children}
    </main>
  )
}
