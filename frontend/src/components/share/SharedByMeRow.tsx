import { Check, ChevronDown, ChevronRight, Copy, Link2, Users } from 'lucide-react'
import { useState } from 'react'

import type { SharedByMeEntry } from '@/api/types'
import { FileIcon } from '@/components/drive/FileIcon'

interface SharedByMeRowProps {
  entry: SharedByMeEntry
  onRemoveUser: (targetUserId: string) => void
  onRemoveLink: (linkId: string) => void
  /** Resolves to the link's URL token, or rejects when it cannot be recovered. */
  onCopyLink: (linkId: string) => Promise<string>
  isBusy: boolean
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function summarise(entry: SharedByMeEntry): string {
  const parts: string[] = []
  if (entry.user_shares.length > 0) {
    parts.push(
      `Shared with ${entry.user_shares.length} ${entry.user_shares.length === 1 ? 'person' : 'people'}`,
    )
  }
  const live = entry.links.filter((l) => l.is_active).length
  if (live > 0) parts.push(`${live} active public ${live === 1 ? 'link' : 'links'}`)
  const dead = entry.links.length - live
  if (dead > 0) parts.push(`${dead} inactive`)
  return parts.join(' · ')
}

/**
 * One shared item per row (proposal §29.5 decision 1) — an item shared with
 * three people and one link stays a single row that expands, rather than four
 * rows that make the list impossible to scan.
 */
export function SharedByMeRow({
  entry,
  onRemoveUser,
  onRemoveLink,
  onCopyLink,
  isBusy,
}: SharedByMeRowProps) {
  const [open, setOpen] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  // Links created before the URL was recoverable have nothing to return. That
  // is a fact about the link, not a transient failure, so the button stays
  // disabled with the reason rather than silently doing nothing.
  const [unrecoverable, setUnrecoverable] = useState<Set<string>>(new Set())
  const { item } = entry

  const copy = async (linkId: string) => {
    try {
      const token = await onCopyLink(linkId)
      await navigator.clipboard?.writeText(`${window.location.origin}/s/${token}`)
      setCopiedId(linkId)
      setTimeout(() => setCopiedId((id) => (id === linkId ? null : id)), 2000)
    } catch {
      setUnrecoverable((prev) => new Set(prev).add(linkId))
    }
  }

  return (
    <li className="border-b last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-accent/50"
      >
        {open ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        )}
        <FileIcon mimeType={item.mime_type} isFolder={item.item_type === 'FOLDER'} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{item.name}</span>
          <span className="block text-xs text-muted-foreground">{summarise(entry)}</span>
        </span>
      </button>

      {open && (
        <div className="space-y-1 px-3 pb-3 pl-10">
          {entry.user_shares.map((share) => (
            <div key={share.target_user_id} className="flex items-center gap-3 text-sm">
              <Users className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate">{share.email}</span>
              <span className="shrink-0 text-xs capitalize text-muted-foreground">
                {share.permission}
              </span>
              <button
                type="button"
                disabled={isBusy}
                onClick={() => onRemoveUser(share.target_user_id)}
                className="shrink-0 rounded px-2 py-1 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          ))}

          {entry.links.map((link) => (
            <div
              key={link.link_id}
              className={`flex items-center gap-3 text-sm ${link.is_active ? '' : 'opacity-60'}`}
            >
              <Link2 className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0 flex-1 text-xs text-muted-foreground">
                Public link
                {link.has_password && ' · password'}
                {link.expires_at && ` · expires ${formatDate(link.expires_at)}`}
                {!link.is_active && ' · inactive'}
              </span>
              <span className="shrink-0 text-xs capitalize text-muted-foreground">
                {link.permission}
              </span>
              {unrecoverable.has(link.link_id) ? (
                <span
                  role="status"
                  className="shrink-0 text-xs text-muted-foreground"
                  title="This link was created before the address could be stored, so it cannot be retrieved."
                >
                  Address unavailable
                </span>
              ) : (
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => void copy(link.link_id)}
                  aria-label={`Copy link for ${item.name}`}
                  className="flex shrink-0 items-center gap-1 rounded px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
                >
                  {copiedId === link.link_id ? (
                    <>
                      <Check className="size-3 text-green-600" aria-hidden="true" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="size-3" aria-hidden="true" />
                      Copy link
                    </>
                  )}
                </button>
              )}
              {/* One action: removing the link is the revocation. Anyone
                  holding the URL loses access immediately, and there is no
                  undo — the row is gone rather than kept as "inactive". */}
              <button
                type="button"
                disabled={isBusy}
                onClick={() => onRemoveLink(link.link_id)}
                className="shrink-0 rounded px-2 py-1 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </li>
  )
}
