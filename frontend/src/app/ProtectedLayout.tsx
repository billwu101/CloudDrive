import { useEffect } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { ChangePasswordReminder } from '@/components/layout/ChangePasswordReminder'
import { useCurrentUserQuery, useLogoutMutation, useQuotaQuery } from '@/hooks/useAuth'
import { useUIStore } from '@/stores/uiStore'

const ROUTE_TITLES: Record<string, string> = {
  '/drive': 'My Drive',
  '/recent': 'Recent',
  '/starred': 'Starred',
  '/shared': 'Shared with me',
  '/trash': 'Trash',
  '/search': 'Search',
  '/settings': 'Account Settings',
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

  const searchQuery =
    location.pathname === '/search'
      ? (new URLSearchParams(location.search).get('q') ?? '')
      : ''

  const handleSearch = (query: string) => {
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`, {
        // Replace when already on /search so back-button skips intermediate queries.
        // Carry the { from } state forward so clearing always knows where to return.
        replace: location.pathname === '/search',
        state: location.pathname !== '/search'
          ? { from: location.pathname + location.search }
          : (location.state as object | null),
      })
    } else if (location.pathname === '/search') {
      const from = (location.state as { from?: string } | null)?.from ?? '/drive'
      navigate(from)
    }
  }

  return (
    <AppShell user={user} quota={quota} onLogout={handleLogout} onSearch={handleSearch} searchValue={searchQuery}>
      {user?.must_change_password && <ChangePasswordReminder />}
      <Outlet />
    </AppShell>
  )
}
