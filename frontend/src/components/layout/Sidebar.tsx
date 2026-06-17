import {
  Clock,
  Cloud,
  HardDrive,
  PanelLeft,
  Share2,
  Sparkles,
  Star,
  Trash2,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

import type { CurrentUserResponse, QuotaResponse } from '@/api/types'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/stores/uiStore'
import { StorageUsageBar } from './StorageUsageBar'
import { UserMenu } from './UserMenu'

const NAV_ITEMS = [
  { to: '/drive', icon: HardDrive, label: 'My Drive' },
  { to: '/recent', icon: Clock, label: 'Recent' },
  { to: '/starred', icon: Star, label: 'Starred' },
  { to: '/shared', icon: Share2, label: 'Shared with me' },
  { to: '/skills', icon: Sparkles, label: 'Skills' },
  { to: '/trash', icon: Trash2, label: 'Trash' },
] as const

interface SidebarProps {
  user?: CurrentUserResponse
  quota?: QuotaResponse
  onLogout?: () => void
}

export function Sidebar({ user, quota, onLogout }: SidebarProps) {
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-border bg-sidebar transition-all duration-200',
        sidebarCollapsed ? 'w-14' : 'w-56',
      )}
      aria-label="Main navigation"
    >
      {/* Header */}
      <div className="flex h-14 items-center justify-between px-3">
        {!sidebarCollapsed && (
          <div className="flex items-center gap-2">
            <Cloud className="size-5 text-primary" aria-hidden="true" />
            <span className="font-semibold text-sm">Cloud Drive</span>
          </div>
        )}
        <button
          type="button"
          className="ml-auto flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={toggleSidebar}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <PanelLeft className="size-4" aria-hidden="true" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-1">
        <ul className="space-y-0.5" role="list">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-2 py-1.5 text-sm transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    isActive
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                      : 'text-sidebar-foreground hover:bg-sidebar-accent/50',
                  )
                }
                title={sidebarCollapsed ? label : undefined}
              >
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                {!sidebarCollapsed && <span>{label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer */}
      <div className="border-t border-border">
        {!sidebarCollapsed && <StorageUsageBar quota={quota} />}
        <div className={cn('px-2 py-2', sidebarCollapsed && 'flex justify-center')}>
          {sidebarCollapsed ? (
            <div className="flex size-7 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
              {user?.username?.charAt(0).toUpperCase() ?? '?'}
            </div>
          ) : (
            <UserMenu user={user} onLogout={onLogout} />
          )}
        </div>
      </div>
    </aside>
  )
}
