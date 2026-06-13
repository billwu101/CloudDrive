import { RotateCcw } from 'lucide-react'

interface RestoreConfirmDialogProps {
  open: boolean
  itemNames: string[]
  loading: boolean
  onConfirm: () => void
  onClose: () => void
}

export function RestoreConfirmDialog({ open, itemNames, loading, onConfirm, onClose }: RestoreConfirmDialogProps) {
  if (!open) return null
  const description = itemNames.length === 1
    ? `"${itemNames[0]}" will be restored.`
    : `${itemNames.length} items will be restored.`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="restore-title"
        className="w-full max-w-sm rounded-lg border bg-popover p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
            <RotateCcw className="size-5 text-primary" aria-hidden="true" />
          </div>
          <div>
            <h2 id="restore-title" className="text-sm font-semibold">Restore?</h2>
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent">Cancel</button>
          <button onClick={onConfirm} disabled={loading} className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50">
            {loading ? 'Restoring…' : 'Restore'}
          </button>
        </div>
      </div>
    </div>
  )
}
