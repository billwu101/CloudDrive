import { Search, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { isApiError } from '@/api/client'
import type { DriveItemResponse } from '@/api/types'
import { FileGrid } from '@/components/drive/FileGrid'
import { FileTable } from '@/components/drive/FileTable'
import { PreviewDialog } from '@/components/preview/PreviewDialog'
import {
  type SearchFilters,
  useDebounce,
  useSearchItems,
  useSemanticSearch,
} from '@/hooks/useSearch'
import { useSetStarred } from '@/hooks/useDrive'
import { useUIStore } from '@/stores/uiStore'

type SearchMode = 'keyword' | 'semantic'

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

  const [mode, setMode] = useState<SearchMode>('keyword')
  const [filters, setFilters] = useState<SearchFilters>({})
  const [previewItemId, setPreviewItemId] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const keyword = useSearchItems(debouncedQuery, filters, page, 20, mode === 'keyword')
  const semantic = useSemanticSearch(debouncedQuery, 20, mode === 'semantic')
  const active = mode === 'keyword' ? keyword : semantic
  const star = useSetStarred()

  const items: DriveItemResponse[] =
    mode === 'keyword'
      ? (keyword.data?.items ?? [])
      : (semantic.data?.map((h) => h.item) ?? [])
  const totalPages = mode === 'keyword' ? (keyword.data?.pages ?? 1) : 1
  const isLoading = active.isLoading
  // A 503 means semantic search isn't enabled on the server — show guidance,
  // not a generic failure.
  const semanticDisabled =
    mode === 'semantic' &&
    semantic.isError &&
    isApiError(semantic.error) &&
    semantic.error.status === 503
  const isError = active.isError && !semanticDisabled
  const refetch = active.refetch

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

        <div className="flex flex-wrap items-center gap-3">
          {/* Mode toggle: keyword vs semantic (meaning-based) */}
          <div className="flex items-center gap-1" role="group" aria-label="Search mode">
            <button
              onClick={() => {
                setMode('keyword')
                setPage(1)
              }}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${mode === 'keyword' ? 'border-primary bg-primary text-primary-foreground' : 'border-input bg-background hover:bg-accent'}`}
            >
              Keyword
            </button>
            <button
              onClick={() => setMode('semantic')}
              className={`flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${mode === 'semantic' ? 'border-primary bg-primary text-primary-foreground' : 'border-input bg-background hover:bg-accent'}`}
            >
              <Sparkles className="size-3" aria-hidden="true" />
              Semantic
            </button>
          </div>

          {/* Type filter pills — keyword mode only */}
          {mode === 'keyword' && (
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
          )}
        </div>
      </div>

      {query && mode === 'semantic' && !semanticDisabled && (
        <p className="-mt-1 text-xs text-muted-foreground">Sorted by relevance to your query.</p>
      )}

      {!query && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Search className="size-12" aria-hidden="true" />
          <p className="text-sm">Enter a search term above</p>
        </div>
      )}

      {query && semanticDisabled && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Sparkles className="size-12" aria-hidden="true" />
          <p className="text-sm">Semantic search isn&apos;t enabled on this server.</p>
          <p className="text-xs">Ask an administrator to enable embeddings, or use Keyword search.</p>
        </div>
      )}

      {query && !semanticDisabled && isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">Searching…</div>
      )}

      {query && isError && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-destructive">
          <p className="text-sm">Search failed.</p>
          <button onClick={() => refetch()} className="text-xs underline">Retry</button>
        </div>
      )}

      {query && !semanticDisabled && !isLoading && !isError && items.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Search className="size-12" aria-hidden="true" />
          <p className="text-sm">No results found</p>
        </div>
      )}

      {query && !semanticDisabled && !isLoading && !isError && items.length > 0 && (
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
