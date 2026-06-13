import { Trash2 } from 'lucide-react'

export function TrashPage() {
  return (
    <div className="flex h-full flex-col gap-4">
      <h1 className="text-lg font-semibold">Trash</h1>
      <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
        <Trash2 className="size-12" aria-hidden="true" />
        <p className="text-sm">Trash is empty</p>
      </div>
    </div>
  )
}
