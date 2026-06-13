import { useState } from 'react'

interface FormProps {
  initialName: string
  loading: boolean
  onConfirm: (name: string) => void
  onClose: () => void
}

function Form({ initialName, loading, onConfirm, onClose }: FormProps) {
  const [name, setName] = useState(initialName)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (trimmed && trimmed !== initialName) onConfirm(trimmed)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onFocus={(e) => e.target.select()}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
      />
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!name.trim() || name.trim() === initialName || loading}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50"
        >
          {loading ? 'Renaming…' : 'Rename'}
        </button>
      </div>
    </form>
  )
}

interface RenameDialogProps {
  open: boolean
  initialName: string
  loading: boolean
  onConfirm: (name: string) => void
  onClose: () => void
}

export function RenameDialog({ open, initialName, loading, onConfirm, onClose }: RenameDialogProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="rename-dialog-title"
        className="w-full max-w-sm rounded-lg border bg-popover p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="rename-dialog-title" className="mb-4 text-sm font-semibold">
          Rename
        </h2>
        <Form key={initialName} initialName={initialName} loading={loading} onConfirm={onConfirm} onClose={onClose} />
      </div>
    </div>
  )
}
