import { Star } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import type { DriveItemResponse } from '@/api/types'
import { FileGrid } from '@/components/drive/FileGrid'
import { FileTable } from '@/components/drive/FileTable'
import { useSetStarred, useStarredItems } from '@/hooks/useDrive'
import { useUIStore } from '@/stores/uiStore'

export function StarredPage() {
  const navigate = useNavigate()
  const viewMode = useUIStore((s) => s.viewMode)
  const selectedIds = useUIStore((s) => s.selectedItemIds)
  const selectItem = useUIStore((s) => s.selectItem)
  const clearSelection = useUIStore((s) => s.clearSelection)

  const { data, isLoading } = useStarredItems()
  const star = useSetStarred()

  const items: DriveItemResponse[] = data?.items ?? []

  const handleDoubleClick = (item: DriveItemResponse) => {
    if (item.item_type === 'FOLDER') navigate(`/drive/folder/${item.id}`)
  }

  const handleStarClick = (item: DriveItemResponse, e: React.MouseEvent) => {
    e.stopPropagation()
    star.mutate({ id: item.id, starred: !item.is_starred })
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <h1 className="text-lg font-semibold">Starred</h1>

      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">Loading…</div>
      )}

      {!isLoading && items.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
          <Star className="size-12" aria-hidden="true" />
          <p className="text-sm">No starred items</p>
        </div>
      )}

      {!isLoading && items.length > 0 && (
        <div onClick={() => clearSelection()} className="flex-1 overflow-auto">
          {viewMode === 'list' ? (
            <FileTable
              items={items}
              selectedIds={selectedIds}
              onItemClick={(item, e) => { e.stopPropagation(); selectItem(item.id, e.metaKey || e.ctrlKey) }}
              onItemDoubleClick={handleDoubleClick}
              onItemContextMenu={(_, e) => e.preventDefault()}
              onStarClick={handleStarClick}
            />
          ) : (
            <FileGrid
              items={items}
              selectedIds={selectedIds}
              onItemClick={(item, e) => { e.stopPropagation(); selectItem(item.id, e.metaKey || e.ctrlKey) }}
              onItemDoubleClick={handleDoubleClick}
              onItemContextMenu={(_, e) => e.preventDefault()}
              onStarClick={handleStarClick}
            />
          )}
        </div>
      )}
    </div>
  )
}
