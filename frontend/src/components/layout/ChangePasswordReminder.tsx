import { AlertTriangle, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

/**
 * Banner shown after login when the account is flagged `must_change_password`
 * (e.g. the password was reset via the forgot-password flow). Dismissible for
 * the current session; reappears on the next load until the user actually
 * changes their password.
 */
export function ChangePasswordReminder() {
  const [dismissed, setDismissed] = useState(false)
  const location = useLocation()

  // Already on the settings page where they can change it — no need to nag.
  if (dismissed || location.pathname === '/settings') return null

  return (
    <div
      role="alert"
      className="flex items-center gap-3 border-b border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900"
    >
      <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
      <p className="flex-1">
        Your password was reset to a temporary one.{' '}
        <Link
          to="/settings"
          className="font-medium underline underline-offset-4 hover:text-amber-950"
        >
          Change it now
        </Link>{' '}
        to keep your account secure.
      </p>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss reminder"
        className="rounded p-1 text-amber-700 hover:bg-amber-100 hover:text-amber-900"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </div>
  )
}
