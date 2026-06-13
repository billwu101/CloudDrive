import { useEffect } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { useCurrentUserQuery, useLogoutMutation, useQuotaQuery } from '@/hooks/useAuth'
import { useUIStore } from '@/stores/uiStore'

const ROUTE_TITLES: Record<string, string> = {
  '/drive': 'My Drive',
  '/recent': 'Recent',
  '/starred': 'Starred',
  '/shared': 'Shared with me',
  '/trash': 'Trash',
  '/search': 'Search',
}

function usePageTitle() {
  const location = useLocation()
  useEffect(() => {
    const base = 'Cloud Drive'
    const segment = '/' + location.pathname.split('/')[1]
    const title = ROUTE_TITLES[segment]
    document.title = title ? `${title} — ${base}` : base
  }, [location.pathname])
}

export function ProtectedLayout() {
  const { data: user } = useCurrentUserQuery()
  const { data: quota } = useQuotaQuery()
  const logoutMutation = useLogoutMutation()
  const navigate = useNavigate()
  const location = useLocation()
  const closeContextMenu = useUIStore((s) => s.closeContextMenu)

  useEffect(() => {
    closeContextMenu()
  }, [location.pathname, closeContextMenu])

  usePageTitle()

  const handleLogout = async () => {
    await logoutMutation.mutateAsync()
    navigate('/login')
  }

  const handleSearch = (query: string) => {
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`)
    }
  }

  return (
    <AppShell user={user} quota={quota} onLogout={handleLogout} onSearch={handleSearch}>
      <Outlet />
    </AppShell>
  )
}
