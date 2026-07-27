import { Share2 } from 'lucide-react'
import { useState } from 'react'

import { SharedByMeRow } from '@/components/share/SharedByMeRow'
import { useDeleteShareLinkRecord, useRemoveUserShare, useSharedByMe } from '@/hooks/useShare'

/**
 * What this user has shared out (proposal §29).
 *
 * The counterpart to "Shared with me". Without it there is no single place to
 * see what has been handed out, so a public link created months ago can stay
 * live without anyone noticing.
 *
 * There is deliberately no "revoke everything" button (§29.5 decision 3):
 * revoking cannot be undone, and one mis-click should not wipe every share.
 */
export function SharedByMePage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = useSharedByMe(page)
  const removeShare = useRemoveUserShare()
  const removeLink = useDeleteShareLinkRecord()

  const entries = data?.items ?? []
  const totalPages = data?.pages ?? 1
  const isBusy = removeShare.isPending || removeLink.isPending

  return (
    <div className="flex h-full flex-col gap-4">
      <h1 className="text-lg font-semibold">Shared by me</h1>

      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      )}

      {isError && (
        <div className="flex flex-1 items-center justify-center text-sm text-destructive">
          Failed to load your shared items.
        </div>
      )}

      {!isLoading && !isError && entries.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Share2 className="size-12" aria-hidden="true" />
          <p className="text-sm">You haven&apos;t shared anything yet</p>
        </div>
      )}

      {!isLoading && !isError && entries.length > 0 && (
        <>
          <ul className="flex-1 overflow-auto rounded-md border">
            {entries.map((entry) => (
              <SharedByMeRow
                key={entry.item.id}
                entry={entry}
                isBusy={isBusy}
                onRemoveUser={(targetUserId) =>
                  removeShare.mutate({ itemId: entry.item.id, targetUserId })
                }
                onRemoveLink={(linkId) => removeLink.mutate(linkId)}
              />
            ))}
          </ul>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 text-sm">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded border px-3 py-1 disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded border px-3 py-1 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
