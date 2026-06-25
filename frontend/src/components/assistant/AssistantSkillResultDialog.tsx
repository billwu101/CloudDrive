import { X } from 'lucide-react'

import type { AssistantSkillExecuteResponse } from '@/api/types'
import { Button } from '@/components/ui/button'

interface AssistantSkillResultDialogProps {
  result: AssistantSkillExecuteResponse | null
  onClose: () => void
}

function labelFor(key: string) {
  return key
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatValue(key: string, value: unknown) {
  if (value === null || value === undefined || value === '') return 'None'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number' && key === 'size_bytes') return formatBytes(value)
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function AssistantSkillResultDialog({
  result,
  onClose,
}: AssistantSkillResultDialogProps) {
  if (!result) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="assistant-skill-result-title"
        className="w-full max-w-md rounded-lg border bg-popover p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id="assistant-skill-result-title" className="text-sm font-semibold">
              {result.message}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">{result.skill_name}</p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close skill result"
            title="Close skill result"
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>
        <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-2 text-sm">
          {Object.entries(result.output).map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-muted-foreground">{labelFor(key)}</dt>
              <dd className="min-w-0 break-words font-medium">{formatValue(key, value)}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}
