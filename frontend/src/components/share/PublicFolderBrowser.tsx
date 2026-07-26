import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Download, File, Folder, Loader2 } from 'lucide-react'

import { listShareChildren } from '@/api/publicShareApi'
import type { PublicItem } from '@/api/types'
import { formatBytes } from '@/lib/uploadLimits'

interface PublicFolderBrowserProps {
  /** Folder currently being shown — the share root, or one of its descendants. */
  folder: PublicItem
  /** Path from the share root down to `folder`, root first. */
  trail: PublicItem[]
  canDownload: boolean
  onOpenFolder: (item: PublicItem) => void
  onOpenFile: (item: PublicItem) => void
  onNavigateTo: (depth: number) => void
  onDownload: (item: PublicItem) => void
}

export function PublicFolderBrowser({
  folder,
  trail,
  canDownload,
  onOpenFolder,
  onOpenFile,
  onNavigateTo,
  onDownload,
}: PublicFolderBrowserProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['public-share', 'children', folder.id],
    queryFn: () => listShareChildren(folder.id),
  })

  return (
    <div className="w-full">
      <nav aria-label="Breadcrumb" className="mb-3 flex flex-wrap items-center gap-1 text-sm">
        {trail.map((crumb, i) => (
          <span key={crumb.id} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="size-3 text-muted-foreground" aria-hidden="true" />}
            <button
              type="button"
              onClick={() => onNavigateTo(i)}
              disabled={i === trail.length - 1}
              className="rounded px-1 hover:bg-accent disabled:font-medium disabled:hover:bg-transparent"
            >
              {crumb.name}
            </button>
          </span>
        ))}
      </nav>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Loader2 className="size-6 animate-spin text-muted-foreground" aria-label="Loading" />
        </div>
      )}

      {isError && <p className="py-10 text-center text-sm text-destructive">Could not load this folder.</p>}

      {data && data.items.length === 0 && (
        <p className="py-10 text-center text-sm text-muted-foreground">This folder is empty.</p>
      )}

      {data && data.items.length > 0 && (
        <ul className="divide-y rounded-md border">
          {data.items.map((item) => (
            <li key={item.id} className="flex items-center gap-3 px-3 py-2">
              <button
                type="button"
                className="flex min-w-0 flex-1 items-center gap-3 text-left"
                onClick={() => (item.item_type === 'FOLDER' ? onOpenFolder(item) : onOpenFile(item))}
              >
                {item.item_type === 'FOLDER' ? (
                  <Folder className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                ) : (
                  <File className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                )}
                <span className="truncate text-sm">{item.name}</span>
              </button>
              {item.item_type === 'FILE' && (
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatBytes(item.size_bytes)}
                </span>
              )}
              {canDownload && item.item_type === 'FILE' && (
                <button
                  type="button"
                  aria-label={`Download ${item.name}`}
                  onClick={() => onDownload(item)}
                  className="shrink-0 rounded p-1 hover:bg-accent"
                >
                  <Download className="size-4" aria-hidden="true" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
