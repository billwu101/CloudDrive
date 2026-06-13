import { Link2 } from 'lucide-react'
import { useParams } from 'react-router-dom'

export function ShareTokenPage() {
  const { shareToken } = useParams<{ shareToken: string }>()

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 text-center">
      <div className="flex size-14 items-center justify-center rounded-full bg-muted">
        <Link2 className="size-7 text-muted-foreground" aria-hidden="true" />
      </div>
      <h1 className="text-xl font-semibold">Shared file</h1>
      <p className="text-sm text-muted-foreground">Token: {shareToken}</p>
      <p className="text-sm text-muted-foreground">
        Share link access will be implemented in Stage 10.
      </p>
    </main>
  )
}
