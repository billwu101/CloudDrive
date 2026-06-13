import { Share2 } from 'lucide-react'

export function SharedPage() {
  return (
    <div className="flex h-full flex-col gap-4">
      <h1 className="text-lg font-semibold">Shared with me</h1>
      <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
        <Share2 className="size-12" aria-hidden="true" />
        <p className="text-sm">Nothing shared with you yet</p>
      </div>
    </div>
  )
}
