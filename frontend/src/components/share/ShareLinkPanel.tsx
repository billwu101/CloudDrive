import { Check, Copy, Link } from 'lucide-react'
import { useState } from 'react'

import type { ShareLinkResponse } from '@/api/types'
import type { Permission } from '@/hooks/useShare'
import { useCreateShareLink } from '@/hooks/useShare'

import { PermissionSelect } from './PermissionSelect'

/** How long a new link lasts unless the sharer changes it. */
const DEFAULT_EXPIRY_DAYS = 7

/**
 * `datetime-local` wants "YYYY-MM-DDTHH:mm" in *local* time, so the ISO string
 * (which is UTC) can't be used directly — it would shift the date by the
 * timezone offset.
 */
function defaultExpiry(): string {
  const when = new Date(Date.now() + DEFAULT_EXPIRY_DAYS * 24 * 60 * 60 * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}` +
    `T${pad(when.getHours())}:${pad(when.getMinutes())}`
  )
}

interface ShareLinkPanelProps {
  itemId: string
  existingLink?: ShareLinkResponse | null
}

export function ShareLinkPanel({ itemId, existingLink }: ShareLinkPanelProps) {
  const [permission, setPermission] = useState<Permission>('viewer')
  const [password, setPassword] = useState('')
  // Pre-filled rather than blank: a link with no expiry never dies, and
  // "leave it empty" is the easiest thing to do by accident. The sharer can
  // still clear or change the date.
  const [expiresAt, setExpiresAt] = useState(defaultExpiry)
  const [copied, setCopied] = useState(false)
  const [activeLink, setActiveLink] = useState<ShareLinkResponse | null>(existingLink ?? null)

  const createLink = useCreateShareLink()

  const handleCreate = async () => {
    const result = await createLink.mutateAsync({
      itemId,
      permission,
      password: password || undefined,
      expiresAt: expiresAt || undefined,
    })
    setActiveLink(result)
  }

  const handleCopy = async () => {
    if (!activeLink?.token) return
    const url = `${window.location.origin}/s/${activeLink.token}`
    await navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (activeLink) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-1.5 rounded-md border bg-muted px-3 py-2 text-sm">
          <Link className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate font-mono text-xs">
            {window.location.origin}/s/{activeLink.token}
          </span>
        </div>
        {/* Copy only. Turning a link off lives in "Shared by me", where every
            link the user has handed out is listed together — the place you go
            to take access away, rather than a dialog you opened to give it. */}
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
            aria-label="Copy link"
          >
            {copied ? <Check className="size-4 text-green-600" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
            {copied ? 'Copied!' : 'Copy link'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <PermissionSelect value={permission} onChange={setPermission} />
        <input
          type="password"
          placeholder="Password (optional)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
          aria-label="Link password (optional)"
        />
      </div>
      <div className="flex items-center gap-2">
        <input
          type="datetime-local"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
          className="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
          aria-label="Link expiry"
        />
        <button
          onClick={handleCreate}
          disabled={createLink.isPending}
          className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50"
        >
          <Link className="size-4" aria-hidden="true" />
          {createLink.isPending ? 'Creating…' : 'Create link'}
        </button>
      </div>
    </div>
  )
}
