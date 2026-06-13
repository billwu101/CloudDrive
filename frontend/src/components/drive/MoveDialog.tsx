import { ChevronRight, Folder, HardDrive, Loader2 } from 'lucide-react'
import { useState } from 'react'

import { useDriveItems } from '@/hooks/useDrive'

interface MoveDialogProps {
  open: boolean
  itemId: string
  loading: boolean
  onConfirm: (targetParentId: string | null) => void
  onClose: () => void
}

function FolderBrowser({
  parentId,
  excludeId,
  selectedId,
  onSelect,
}: {
  parentId?: string
  excludeId: string
  selectedId: string | null
  onSelect: (id: string | null) => void
}) {
  const { data, isLoading } = useDriveItems(parentId)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const folders = (data?.items ?? []).filter((i) => i.item_type === 'FOLDER' && i.id !== excludeId)

  if (isLoading) return <Loader2 className="size-4 animate-spin text-muted-foreground" />

  return (
    <ul className="space-y-0.5">
      {folders.map((f) => (
        <li key={f.id}>
          <div className="flex items-center gap-1">
            <button
              aria-label={`Expand ${f.name}`}
              onClick={() => setExpandedId(expandedId === f.id ? null : f.id)}
              className="rounded p-0.5 hover:bg-accent"
            >
              <ChevronRight
                className={`size-3 text-muted-foreground transition-transform ${expandedId === f.id ? 'rotate-90' : ''}`}
                aria-hidden="true"
              />
            </button>
            <button
              onClick={() => onSelect(f.id)}
              className={`flex flex-1 items-center gap-1.5 rounded px-2 py-1 text-left text-sm transition-colors hover:bg-accent ${selectedId === f.id ? 'bg-accent font-medium' : ''}`}
            >
              <Folder className="size-4 shrink-0 text-blue-500" aria-hidden="true" />
              <span className="truncate">{f.name}</span>
            </button>
          </div>
          {expandedId === f.id && (
            <div className="ml-4 mt-0.5">
              <FolderBrowser
                parentId={f.id}
                excludeId={excludeId}
                selectedId={selectedId}
                onSelect={onSelect}
              />
            </div>
          )}
        </li>
      ))}
      {folders.length === 0 && !isLoading && (
        <li className="py-1 pl-5 text-xs text-muted-foreground">No folders</li>
      )}
    </ul>
  )
}

export function MoveDialog({ open, itemId, loading, onConfirm, onClose }: MoveDialogProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="move-dialog-title"
        className="flex w-full max-w-sm flex-col rounded-lg border bg-popover shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b px-5 py-4">
          <h2 id="move-dialog-title" className="text-sm font-semibold">
            Move to…
          </h2>
        </div>

        <div className="max-h-72 overflow-y-auto p-3">
          <button
            onClick={() => setSelectedId(null)}
            className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-sm transition-colors hover:bg-accent ${selectedId === null ? 'bg-accent font-medium' : ''}`}
          >
            <HardDrive className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            My Drive (root)
          </button>
          <div className="ml-4 mt-0.5">
            <FolderBrowser parentId={undefined} excludeId={itemId} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(selectedId)}
            disabled={loading}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50"
          >
            {loading ? 'Moving…' : 'Move here'}
          </button>
        </div>
      </div>
    </div>
  )
}
