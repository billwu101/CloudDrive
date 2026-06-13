import { CheckCircle2, Loader2, RefreshCw, X, XCircle } from 'lucide-react'

import type { UploadTask } from '@/stores/uploadStore'

interface UploadTaskItemProps {
  task: UploadTask
  onCancel: (id: string) => void
  onRetry: (task: UploadTask) => void
  onRemove: (id: string) => void
}

export function UploadTaskItem({ task, onCancel, onRetry, onRemove }: UploadTaskItemProps) {
  const { id, file, progress, status, error } = task

  return (
    <li className="flex items-center gap-3 rounded-md border bg-background px-3 py-2 text-sm">
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium" title={file.name}>
          {file.name}
        </p>

        {status === 'uploading' && (
          <div className="mt-1">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-200"
                style={{ width: `${progress}%` }}
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">{progress}%</p>
          </div>
        )}

        {status === 'failed' && (
          <p className="mt-0.5 text-xs text-destructive">{error}</p>
        )}

        {status === 'completed' && (
          <p className="mt-0.5 text-xs text-green-600">Uploaded</p>
        )}

        {status === 'canceled' && (
          <p className="mt-0.5 text-xs text-muted-foreground">Canceled</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {status === 'uploading' && (
          <>
            <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden="true" />
            <button
              aria-label="Cancel upload"
              onClick={() => onCancel(id)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:text-destructive"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </>
        )}

        {status === 'completed' && (
          <>
            <CheckCircle2 className="size-4 text-green-600" aria-hidden="true" />
            <button
              aria-label="Dismiss"
              onClick={() => onRemove(id)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </>
        )}

        {status === 'failed' && (
          <>
            <XCircle className="size-4 text-destructive" aria-hidden="true" />
            <button
              aria-label="Retry upload"
              onClick={() => onRetry(task)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:text-primary"
            >
              <RefreshCw className="size-4" aria-hidden="true" />
            </button>
            <button
              aria-label="Dismiss"
              onClick={() => onRemove(id)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </>
        )}

        {(status === 'pending' || status === 'canceled') && (
          <button
            aria-label="Dismiss"
            onClick={() => onRemove(id)}
            className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>
    </li>
  )
}
