import { Search } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import type { DriveItemResponse } from '@/api/types'
import { FileGrid } from '@/components/drive/FileGrid'
import { FileTable } from '@/components/drive/FileTable'
import { PreviewDialog } from '@/components/preview/PreviewDialog'
import { type SearchFilters, useDebounce, useSearchItems } from '@/hooks/useSearch'
import { useSetStarred } from '@/hooks/useDrive'
import { useUIStore } from '@/stores/uiStore'

const ITEM_TYPE_OPTIONS = [
  { label: 'All', value: undefined },
  { label: 'Files', value: 'FILE' as const },
  { label: 'Folders', value: 'FOLDER' as const },
]

export function SearchPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const query = params.get('q') ?? ''
  const debouncedQuery = useDebounce(query, 300)

  const viewMode = useUIStore((s) => s.viewMode)
  const selectedIds = useUIStore((s) => s.selectedItemIds)
  const selectItem = useUIStore((s) => s.selectItem)
  const selectAll = useUIStore((s) => s.selectAll)
  const clearSelection = useUIStore((s) => s.clearSelection)

  const [filters, setFilters] = useState<SearchFilters>({})
  const [previewItemId, setPreviewItemId] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const { data, isLoading, isError, refetch } = useSearchItems(debouncedQuery, filters, page)
  const star = useSetStarred()

  const items: DriveItemResponse[] = data?.items ?? []
  const totalPages = data?.pages ?? 1

  const handleDoubleClick = (item: DriveItemResponse) => {
    if (item.item_type === 'FOLDER') {
      navigate(`/drive/folder/${item.id}`)
    } else {
      setPreviewItemId(item.id)
    }
  }

  const handleStarClick = (item: DriveItemResponse, e: React.MouseEvent) => {
    e.stopPropagation()
    star.mutate({ id: item.id, starred: !item.is_starred })
  }

  const handleCheckboxClick = (item: DriveItemResponse, e: React.MouseEvent) => {
    e.stopPropagation()
    selectItem(item.id, true)
  }

  const handleSelectAll = () => {
    if (items.every((i) => selectedIds.has(i.id))) {
      clearSelection()
    } else {
      selectAll(items.map((i) => i.id))
    }
  }

  const handleTypeFilter = (value: SearchFilters['itemType']) => {
    setFilters((f) => ({ ...f, itemType: value }))
    setPage(1)
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold">
          {query ? `Results for "${query}"` : 'Search'}
        </h1>

        {/* Type filter pills */}
        <div className="flex items-center gap-1" role="group" aria-label="Filter by type">
          {ITEM_TYPE_OPTIONS.map(({ label, value }) => (
            <button
              key={label}
              onClick={() => handleTypeFilter(value)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${filters.itemType === value ? 'border-primary bg-primary text-primary-foreground' : 'border-input bg-background hover:bg-accent'}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {!query && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Search className="size-12" aria-hidden="true" />
          <p className="text-sm">Enter a search term above</p>
        </div>
      )}

      {query && isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">Searching…</div>
      )}

      {query && isError && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-destructive">
          <p className="text-sm">Search failed.</p>
          <button onClick={() => refetch()} className="text-xs underline">Retry</button>
        </div>
      )}

      {query && !isLoading && !isError && items.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Search className="size-12" aria-hidden="true" />
          <p className="text-sm">No results found</p>
        </div>
      )}

      {query && !isLoading && !isError && items.length > 0 && (
        <>
          <div onClick={() => clearSelection()} className="flex-1 overflow-auto">
            {viewMode === 'list' ? (
              <FileTable
                items={items}
                selectedIds={selectedIds}
                onItemClick={(item, e) => { e.stopPropagation(); selectItem(item.id, e.metaKey || e.ctrlKey) }}
                onItemDoubleClick={handleDoubleClick}
                onItemContextMenu={(_, e) => e.preventDefault()}
                onStarClick={handleStarClick}
                onCheckboxClick={handleCheckboxClick}
                onSelectAll={handleSelectAll}
              />
            ) : (
              <FileGrid
                items={items}
                selectedIds={selectedIds}
                onItemClick={(item, e) => { e.stopPropagation(); selectItem(item.id, e.metaKey || e.ctrlKey) }}
                onItemDoubleClick={handleDoubleClick}
                onItemContextMenu={(_, e) => e.preventDefault()}
                onStarClick={handleStarClick}
                onCheckboxClick={handleCheckboxClick}
              />
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 text-sm">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded border px-3 py-1 disabled:opacity-40 hover:bg-accent"
              >
                Previous
              </button>
              <span className="text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded border px-3 py-1 disabled:opacity-40 hover:bg-accent"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      <PreviewDialog itemId={previewItemId} onClose={() => setPreviewItemId(null)} />
    </div>
  )
}
