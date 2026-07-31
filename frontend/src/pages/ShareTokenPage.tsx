import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FileWarning, FolderArchive, Loader2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { isApiError } from '@/api/client'
import {
  downloadSharedArchive,
  downloadSharedItem,
  fetchSharePreviewUrl,
  openShareSession,
  refreshShareSession,
  setShareCredential,
} from '@/api/publicShareApi'
import type { PublicItem, PublicSession } from '@/api/types'
import { PublicFolderBrowser } from '@/components/share/PublicFolderBrowser'
import { PublicPasswordForm } from '@/components/share/PublicPasswordForm'
import { formatBytes } from '@/lib/uploadLimits'

/**
 * Guest view for a public share link (proposal §28).
 *
 * Not wrapped in RequireAuth — the whole point is that the visitor has no
 * account. The credential returned by the session endpoint lives in memory
 * only (see publicShareApi), so a reload re-validates from scratch.
 */

/** One message for every failure, so a wrong password and a bad token look alike. */
const INVALID_MESSAGE = 'This link is invalid or no longer available.'

const sessionKey = (token: string) => ['public-share', 'session', token] as const

function needsPassword(err: unknown): boolean {
  return isApiError(err) && err.code === 'SHARE_LINK_PASSWORD_REQUIRED'
}

export function ShareTokenPage() {
  const { shareToken = '' } = useParams<{ shareToken: string }>()
  const qc = useQueryClient()
  // Empty until the visitor navigates; the share root fills in below, so there
  // is no effect syncing state that the render can already work out.
  const [trail, setTrail] = useState<PublicItem[]>([])
  const [previewOf, setPreviewOf] = useState<PublicItem | null>(null)

  // First contact goes out without a password: links that have none open
  // straight away, which is what keeps the password step out of the way when
  // it isn't needed. Only a password-protected link answers with a 401.
  const probe = useQuery({
    queryKey: sessionKey(shareToken),
    queryFn: () => openShareSession(shareToken),
    enabled: !!shareToken,
    retry: false,
    staleTime: Infinity,
  })

  const unlock = useMutation({
    mutationFn: (password: string) => openShareSession(shareToken, password),
    onSuccess: (session) => qc.setQueryData(sessionKey(shareToken), session),
  })

  const session = probe.data ?? unlock.data
  useEffect(() => () => setShareCredential(null), [])

  // Keep the credential alive while the visitor is still browsing, so a long
  // look at a folder doesn't end in a re-prompt for the password.
  const expiresIn = session?.expires_in
  useEffect(() => {
    if (!shareToken || expiresIn === undefined) return
    const timer = setTimeout(
      () => {
        refreshShareSession(shareToken)
          .then((next) => qc.setQueryData(sessionKey(shareToken), next))
          .catch(() => qc.setQueryData(sessionKey(shareToken), undefined))
      },
      Math.max(30, expiresIn - 60) * 1000,
    )
    return () => clearTimeout(timer)
  }, [shareToken, expiresIn, qc])

  if (probe.isPending) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" aria-label="Opening link" />
      </main>
    )
  }

  if (!session) {
    // A locked link and a dead one are the same screen, on purpose: telling
    // them apart would let someone probe for valid tokens.
    if (needsPassword(probe.error)) {
      return (
        <main className="flex min-h-screen items-center justify-center p-6">
          <PublicPasswordForm
            isPending={unlock.isPending}
            error={unlock.isError ? INVALID_MESSAGE : null}
            onSubmit={(password) => unlock.mutate(password)}
          />
        </main>
      )
    }
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 text-center">
        <div className="flex size-14 items-center justify-center rounded-full bg-muted">
          <FileWarning className="size-7 text-muted-foreground" aria-hidden="true" />
        </div>
        <h1 className="text-xl font-semibold">Link unavailable</h1>
        <p className="text-sm text-muted-foreground">{INVALID_MESSAGE}</p>
      </main>
    )
  }

  return (
    <SharedContent
      session={session}
      trail={trail.length > 0 ? trail : [session.item]}
      onTrailChange={setTrail}
      previewOf={previewOf}
      onPreview={setPreviewOf}
    />
  )
}

interface SharedContentProps {
  session: PublicSession
  trail: PublicItem[]
  onTrailChange: (next: PublicItem[]) => void
  previewOf: PublicItem | null
  onPreview: (item: PublicItem | null) => void
}

function SharedContent({
  session,
  trail,
  onTrailChange,
  previewOf,
  onPreview,
}: SharedContentProps) {
  // Download is everything above viewer — writing `=== 'downloader'` here once
  // left editor links looking read-only (design §5.9.6 point 8).
  const canDownload = session.permission !== 'viewer'
  const canEdit = session.permission === 'editor'
  const current = trail[trail.length - 1] ?? session.item
  const isFolder = session.item.item_type === 'FOLDER'

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold">{session.item.name}</h1>
          <p className="text-sm text-muted-foreground">
            Shared with you
            {!isFolder && ` · ${formatBytes(session.item.size_bytes)}`}
            {session.permission === 'viewer' && ' · View only'}
            {canEdit && ' · Can edit'}
          </p>
        </div>
        {canDownload && (
          <button
            type="button"
            onClick={() =>
              isFolder
                ? void downloadSharedArchive(session.item.name)
                : void downloadSharedItem(session.item.id, session.item.name)
            }
            className="flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
          >
            {isFolder ? (
              <>
                <FolderArchive className="size-4" aria-hidden="true" />
                Download folder
              </>
            ) : (
              <>
                <Download className="size-4" aria-hidden="true" />
                Download
              </>
            )}
          </button>
        )}
      </header>

      {isFolder ? (
        <PublicFolderBrowser
          folder={current}
          trail={trail}
          canDownload={canDownload}
          canEdit={canEdit}
          onOpenFolder={(item) => onTrailChange([...trail, item])}
          onOpenFile={(item) => onPreview(item)}
          onNavigateTo={(depth) => onTrailChange(trail.slice(0, depth + 1))}
          onDownload={(item) => void downloadSharedItem(item.id, item.name)}
        />
      ) : (
        <SharedFilePreview item={session.item} />
      )}

      {previewOf && (
        <div className="fixed inset-0 z-50 flex flex-col bg-background/95 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="truncate text-sm font-medium">{previewOf.name}</span>
            <button
              type="button"
              aria-label="Close preview"
              onClick={() => onPreview(null)}
              className="rounded p-1 hover:bg-accent"
            >
              <X className="size-5" aria-hidden="true" />
            </button>
          </div>
          <div className="min-h-0 flex-1">
            <SharedFilePreview item={previewOf} />
          </div>
        </div>
      )}
    </main>
  )
}

/** Renders one shared file inline, fetching its bytes through the guest client. */
function SharedFilePreview({ item }: { item: PublicItem }) {
  const supported = item.preview_type !== 'unsupported'
  const { data: url, isError } = useQuery({
    queryKey: ['public-share', 'preview', item.id],
    queryFn: () => fetchSharePreviewUrl(item.id),
    enabled: supported,
    retry: false,
    staleTime: Infinity,
    gcTime: 0,
  })

  // Blob URLs leak until revoked, and the query cache won't do it for us.
  useEffect(() => {
    if (!url) return
    return () => URL.revokeObjectURL(url)
  }, [url])

  if (!supported) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        No preview available for this file type.
      </p>
    )
  }
  if (isError) {
    return <p className="py-10 text-center text-sm text-destructive">Could not load preview.</p>
  }
  if (!url) {
    return (
      <div className="flex justify-center py-10">
        <Loader2
          className="size-6 animate-spin text-muted-foreground"
          aria-label="Loading preview"
        />
      </div>
    )
  }

  switch (item.preview_type) {
    case 'image':
      return (
        <img src={url} alt={item.name} className="mx-auto max-h-[70vh] rounded object-contain" />
      )
    case 'video':
      return <video src={url} controls className="mx-auto max-h-[70vh] w-full rounded" />
    case 'audio':
      return <audio src={url} controls className="w-full" />
    default:
      // pdf, document (server-converted to PDF), text and markdown all render
      // acceptably in the browser's own viewer.
      return <iframe src={url} title={item.name} className="h-[70vh] w-full rounded border" />
  }
}
