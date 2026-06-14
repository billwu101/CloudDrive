import { Trash2 } from 'lucide-react'

interface MultiFileContextMenuProps {
  count: number
  position: { x: number; y: number }
  onClose: () => void
  onTrash: () => void
}

export function MultiFileContextMenu({ count, position, onClose, onTrash }: MultiFileContextMenuProps) {
  return (
    <>
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        onContextMenu={(e) => { e.preventDefault(); onClose() }}
        aria-hidden="true"
      />
      <div
        role="menu"
        className="fixed z-50 min-w-44 rounded-md border bg-popover p-1 shadow-md"
        style={{ top: position.y, left: position.x }}
      >
        <div className="border-b px-3 py-1.5 mb-1 text-xs text-muted-foreground">
          {count} items selected
        </div>
        <button
          role="menuitem"
          onClick={(e) => { e.stopPropagation(); onTrash(); onClose() }}
          className="flex w-full items-center gap-2 rounded-sm px-3 py-1.5 text-left text-sm text-destructive transition-colors hover:bg-accent"
        >
          <Trash2 className="size-4" aria-hidden="true" />
          Move to trash
        </button>
      </div>
    </>
  )
}
