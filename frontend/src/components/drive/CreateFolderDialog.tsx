import { useRef, useState } from 'react'

interface FormProps {
  loading: boolean
  onConfirm: (name: string) => void
  onClose: () => void
}

function Form({ loading, onConfirm, onClose }: FormProps) {
  const [name, setName] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (trimmed) onConfirm(trimmed)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <input
        ref={inputRef}
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Folder name"
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
          disabled={!name.trim() || loading}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50"
        >
          {loading ? 'Creating…' : 'Create'}
        </button>
      </div>
    </form>
  )
}

interface CreateFolderDialogProps {
  open: boolean
  loading: boolean
  onConfirm: (name: string) => void
  onClose: () => void
}

export function CreateFolderDialog({ open, loading, onConfirm, onClose }: CreateFolderDialogProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-folder-title"
        className="w-full max-w-sm rounded-lg border bg-popover p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="create-folder-title" className="mb-4 text-sm font-semibold">
          New folder
        </h2>
        <Form loading={loading} onConfirm={onConfirm} onClose={onClose} />
      </div>
    </div>
  )
}
