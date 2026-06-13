import type { ReactNode } from 'react'

import type { CurrentUserResponse, QuotaResponse } from '@/api/types'
import { MainContent } from './MainContent'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

interface AppShellProps {
  children: ReactNode
  title?: string
  user?: CurrentUserResponse
  quota?: QuotaResponse
  onLogout?: () => void
  onSearch?: (query: string) => void
}

export function AppShell({
  children,
  title,
  user,
  quota,
  onLogout,
  onSearch,
}: AppShellProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar user={user} quota={quota} onLogout={onLogout} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar title={title} onSearch={onSearch} />
        <MainContent>{children}</MainContent>
      </div>
    </div>
  )
}
