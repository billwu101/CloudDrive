import { Download, FolderPlus, Trash2 } from 'lucide-react'

interface DriveToolbarProps {
  selectedCount: number
  onNewFolder: () => void
  onDownloadSelected: () => void
  onTrashSelected: () => void
}

export function DriveToolbar({
  selectedCount,
  onNewFolder,
  onDownloadSelected,
  onTrashSelected,
}: DriveToolbarProps) {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onNewFolder}
        className="flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <FolderPlus className="size-4" aria-hidden="true" />
        New folder
      </button>

      {selectedCount > 0 && (
        <>
          <button
            onClick={onDownloadSelected}
            className="flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download className="size-4" aria-hidden="true" />
            Download ({selectedCount})
          </button>

          <button
            onClick={onTrashSelected}
            className="flex items-center gap-1.5 rounded-md border border-destructive/30 px-3 py-1.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Trash2 className="size-4" aria-hidden="true" />
            Trash ({selectedCount})
          </button>
        </>
      )}
    </div>
  )
}
