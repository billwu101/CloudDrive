import { Lock } from 'lucide-react'
import { useState } from 'react'

interface PublicPasswordFormProps {
  onSubmit: (password: string) => void
  isPending: boolean
  error: string | null
}

export function PublicPasswordForm({ onSubmit, isPending, error }: PublicPasswordFormProps) {
  const [password, setPassword] = useState('')

  return (
    <form
      className="w-full max-w-sm space-y-4 text-center"
      onSubmit={(e) => {
        e.preventDefault()
        if (password) onSubmit(password)
      }}
    >
      <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-muted">
        <Lock className="size-7 text-muted-foreground" aria-hidden="true" />
      </div>
      <div>
        <h1 className="text-xl font-semibold">This link is password protected</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter the password you were given to open it.
        </p>
      </div>
      <input
        type="password"
        aria-label="Password"
        autoFocus
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full rounded-md border bg-background px-3 py-2 text-sm"
      />
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={!password || isPending}
        className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
      >
        {isPending ? 'Checking…' : 'Open'}
      </button>
    </form>
  )
}
