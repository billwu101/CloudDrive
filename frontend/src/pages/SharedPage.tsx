import { Share2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { ShareResponse } from '@/api/types'
import { useSharedWithMe } from '@/hooks/useShare'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function SharedPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = useSharedWithMe(page)
  const items: ShareResponse[] = data?.items ?? []
  const totalPages = data?.pages ?? 1

  return (
    <div className="flex h-full flex-col gap-4">
      <h1 className="text-lg font-semibold">Shared with me</h1>

      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">Loading…</div>
      )}

      {isError && (
        <div className="flex flex-1 items-center justify-center text-sm text-destructive">Failed to load shared items.</div>
      )}

      {!isLoading && !isError && items.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Share2 className="size-12" aria-hidden="true" />
          <p className="text-sm">Nothing shared with you yet</p>
        </div>
      )}

      {!isLoading && !isError && items.length > 0 && (
        <>
          <div className="flex-1 overflow-auto">
            <table className="w-full table-fixed border-collapse text-left">
              <thead>
                <tr className="border-b text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pl-3 pr-3">Item</th>
                  <th className="w-28 py-2 pr-3">Permission</th>
                  <th className="w-32 py-2 pr-3">Shared on</th>
                </tr>
              </thead>
              <tbody>
                {items.map((share) => (
                  <tr
                    key={share.id}
                    onClick={() => navigate(`/drive/folder/${share.item_id}`)}
                    className="cursor-pointer border-b transition-colors last:border-b-0 hover:bg-accent/50"
                  >
                    <td className="truncate py-2 pl-3 pr-3 text-sm font-medium">
                      {share.item_id}
                    </td>
                    <td className="py-2 pr-3 text-sm capitalize text-muted-foreground">
                      {share.permission}
                    </td>
                    <td className="py-2 pr-3 text-sm text-muted-foreground whitespace-nowrap">
                      {formatDate(share.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 text-sm">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded border px-3 py-1 disabled:opacity-40 hover:bg-accent">Previous</button>
              <span className="text-muted-foreground">Page {page} of {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="rounded border px-3 py-1 disabled:opacity-40 hover:bg-accent">Next</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
