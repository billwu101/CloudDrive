import { RotateCcw, Trash2 } from 'lucide-react'

interface TrashToolbarProps {
  selectedCount: number
  totalItems: number
  onRestoreSelected: () => void
  onDeleteSelected: () => void
  onEmptyTrash: () => void
}

export function TrashToolbar({
  selectedCount,
  totalItems,
  onRestoreSelected,
  onDeleteSelected,
  onEmptyTrash,
}: TrashToolbarProps) {
  return (
    <div className="flex items-center gap-2">
      {selectedCount > 0 ? (
        <>
          <button
            onClick={onRestoreSelected}
            className="flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <RotateCcw className="size-4" aria-hidden="true" />
            Restore ({selectedCount})
          </button>
          <button
            onClick={onDeleteSelected}
            className="flex items-center gap-1.5 rounded-md border border-destructive/30 px-3 py-1.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Trash2 className="size-4" aria-hidden="true" />
            Delete forever ({selectedCount})
          </button>
        </>
      ) : (
        totalItems > 0 && (
          <button
            onClick={onEmptyTrash}
            className="flex items-center gap-1.5 rounded-md border border-destructive/30 px-3 py-1.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Trash2 className="size-4" aria-hidden="true" />
            Empty trash
          </button>
        )
      )}
    </div>
  )
}
