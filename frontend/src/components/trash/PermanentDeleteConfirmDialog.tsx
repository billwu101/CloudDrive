import { AlertTriangle } from 'lucide-react'

interface PermanentDeleteConfirmDialogProps {
  open: boolean
  itemNames: string[]
  loading: boolean
  onConfirm: () => void
  onClose: () => void
}

export function PermanentDeleteConfirmDialog({ open, itemNames, loading, onConfirm, onClose }: PermanentDeleteConfirmDialogProps) {
  if (!open) return null
  const description = itemNames.length === 1
    ? `"${itemNames[0]}" will be permanently deleted and cannot be recovered.`
    : `${itemNames.length} items will be permanently deleted and cannot be recovered.`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="perm-delete-title"
        className="w-full max-w-sm rounded-lg border bg-popover p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
            <AlertTriangle className="size-5 text-destructive" aria-hidden="true" />
          </div>
          <div>
            <h2 id="perm-delete-title" className="text-sm font-semibold">Delete forever?</h2>
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent">Cancel</button>
          <button onClick={onConfirm} disabled={loading} className="rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-destructive/80 disabled:opacity-50">
            {loading ? 'Deleting…' : 'Delete forever'}
          </button>
        </div>
      </div>
    </div>
  )
}
