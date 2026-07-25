import {
  CheckCircle2,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Upload,
  X,
  XCircle,
} from 'lucide-react'
import { useRef } from 'react'

import type { UploadTask } from '@/stores/uploadStore'

interface UploadTaskItemProps {
  task: UploadTask
  onCancel: (id: string) => void
  onRetry: (task: UploadTask) => void
  onRemove: (id: string) => void
  onPause: (id: string) => void
  onContinue: (id: string) => void
  onResumeFile: (id: string, file: File) => void
}

export function UploadTaskItem({
  task,
  onCancel,
  onRetry,
  onRemove,
  onPause,
  onContinue,
  onResumeFile,
}: UploadTaskItemProps) {
  const { id, fileName, progress, status, error } = task
  const isChunked = task.sessionId !== undefined || status === 'needs_file'
  const fileInputRef = useRef<HTMLInputElement>(null)

  return (
    <li className="flex items-center gap-3 rounded-md border bg-background px-3 py-2 text-sm">
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium" title={fileName}>
          {fileName}
        </p>

        {(status === 'uploading' || status === 'paused') && (
          <div className="mt-1">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full transition-all duration-200 ${
                  status === 'paused' ? 'bg-muted-foreground' : 'bg-primary'
                }`}
                style={{ width: `${progress}%` }}
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {progress}%{status === 'paused' ? ' · Paused' : ''}
            </p>
          </div>
        )}

        {status === 'queued' && <p className="mt-0.5 text-xs text-muted-foreground">Waiting…</p>}

        {status === 'needs_file' && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            Reselect this file to resume the upload
          </p>
        )}

        {status === 'failed' && <p className="mt-0.5 text-xs text-destructive">{error}</p>}

        {status === 'completed' && <p className="mt-0.5 text-xs text-green-600">Uploaded</p>}

        {status === 'canceled' && (
          <p className="mt-0.5 text-xs text-muted-foreground">Canceled</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {status === 'uploading' && (
          <>
            <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden="true" />
            {isChunked && (
              <button
                aria-label="Pause upload"
                onClick={() => onPause(id)}
                className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
              >
                <Pause className="size-4" aria-hidden="true" />
              </button>
            )}
            <button
              aria-label="Cancel upload"
              onClick={() => onCancel(id)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:text-destructive"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </>
        )}

        {status === 'paused' && (
          <>
            <button
              aria-label="Continue upload"
              onClick={() => onContinue(id)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:text-primary"
            >
              <Play className="size-4" aria-hidden="true" />
            </button>
            <button
              aria-label="Cancel upload"
              onClick={() => onCancel(id)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:text-destructive"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </>
        )}

        {status === 'needs_file' && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              aria-hidden="true"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) onResumeFile(id, file)
                e.target.value = ''
              }}
            />
            <button
              aria-label="Select file to resume"
              onClick={() => fileInputRef.current?.click()}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:text-primary"
            >
              <Upload className="size-4" aria-hidden="true" />
            </button>
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
            {task.file !== null && (
              <button
                aria-label="Retry upload"
                onClick={() => onRetry(task)}
                className="rounded p-0.5 text-muted-foreground transition-colors hover:text-primary"
              >
                <RefreshCw className="size-4" aria-hidden="true" />
              </button>
            )}
            <button
              aria-label="Dismiss"
              onClick={() => onRemove(id)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </>
        )}

        {(status === 'pending' || status === 'queued' || status === 'canceled') && (
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
