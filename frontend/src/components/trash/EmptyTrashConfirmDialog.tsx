import { Trash2 } from 'lucide-react'

interface EmptyTrashConfirmDialogProps {
  open: boolean
  loading: boolean
  onConfirm: () => void
  onClose: () => void
}

export function EmptyTrashConfirmDialog({ open, loading, onConfirm, onClose }: EmptyTrashConfirmDialogProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="empty-trash-title"
        className="w-full max-w-sm rounded-lg border bg-popover p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
            <Trash2 className="size-5 text-destructive" aria-hidden="true" />
          </div>
          <div>
            <h2 id="empty-trash-title" className="text-sm font-semibold">Empty trash?</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              All items in trash will be permanently deleted. This action cannot be undone.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent">Cancel</button>
          <button onClick={onConfirm} disabled={loading} className="rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-destructive/80 disabled:opacity-50">
            {loading ? 'Emptying…' : 'Empty trash'}
          </button>
        </div>
      </div>
    </div>
  )
}
