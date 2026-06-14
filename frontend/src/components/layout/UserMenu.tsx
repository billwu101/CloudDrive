import { LogOut, Settings, User } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { CurrentUserResponse } from '@/api/types'
import { useAuthStore } from '@/stores/authStore'

interface UserMenuProps {
  user: CurrentUserResponse | undefined
  onLogout?: () => void
}

export function UserMenu({ user, onLogout }: UserMenuProps) {
  const [open, setOpen] = useState(false)
  const clearToken = useAuthStore((s) => s.clearToken)

  const handleLogout = () => {
    clearToken()
    onLogout?.()
    setOpen(false)
  }

  return (
    <div className="relative">
      <button
        type="button"
        className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <div className="flex size-7 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
          {user?.username?.charAt(0).toUpperCase() ?? <User className="size-4" />}
        </div>
        <span className="max-w-28 truncate">{user?.username ?? '...'}</span>
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            role="menu"
            className="absolute bottom-full left-0 z-20 mb-1 w-48 rounded-md border border-border bg-popover py-1 shadow-md"
          >
            {user && (
              <div className="border-b border-border px-3 py-2">
                <p className="truncate text-xs font-medium">{user.username}</p>
                <p className="truncate text-xs text-muted-foreground">{user.email}</p>
              </div>
            )}
            <Link
              to="/settings"
              role="menuitem"
              className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-foreground hover:bg-muted"
              onClick={() => setOpen(false)}
            >
              <Settings className="size-4" aria-hidden="true" />
              Account settings
            </Link>
            <button
              type="button"
              role="menuitem"
              className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-destructive hover:bg-muted"
              onClick={handleLogout}
            >
              <LogOut className="size-4" aria-hidden="true" />
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  )
}
