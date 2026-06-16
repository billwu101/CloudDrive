import { Check, X } from 'lucide-react'

import type { WorkflowStepResult } from '@/api/types'

function formatBytes(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${unit === 0 ? value : value.toFixed(1)} ${units[unit]}`
}

function names(items: unknown[]): string {
  const labels = items
    .map((it) => (it && typeof it === 'object' ? (it as Record<string, unknown>).name : it))
    .filter((n): n is string => typeof n === 'string')
  if (labels.length === 0) return ''
  const shown = labels.slice(0, 5).join(', ')
  return labels.length > 5 ? `${shown}, …` : shown
}

function withCount(total: number, listing: string): string {
  const head = `${total} item${total === 1 ? '' : 's'}`
  return listing ? `${head}: ${listing}` : head
}

function summarize(result: WorkflowStepResult): string {
  if (!result.ok) return result.error ?? 'Failed'
  const output = result.output
  if (output && typeof output === 'object' && !Array.isArray(output)) {
    const o = output as Record<string, unknown>
    if (typeof o.available_bytes === 'number' && typeof o.quota_bytes === 'number') {
      const pct = typeof o.used_percent === 'number' ? Math.round(o.used_percent) : 0
      return `${formatBytes(o.available_bytes)} free of ${formatBytes(o.quota_bytes)} (${pct}% used)`
    }
    if (Array.isArray(o.items)) {
      const total = typeof o.total === 'number' ? o.total : o.items.length
      return withCount(total, names(o.items))
    }
    if (typeof o.name === 'string') return o.name
  }
  if (Array.isArray(output)) return withCount(output.length, names(output))
  return 'Done'
}

export function StepResultList({ results }: { results: WorkflowStepResult[] }) {
  if (results.length === 0) return null
  return (
    <ul className="mt-2 space-y-1 border-t border-border/60 pt-2 text-xs">
      {results.map((result) => (
        <li key={result.index} className="flex items-start gap-1.5">
          {result.ok ? (
            <Check className="mt-0.5 size-3 shrink-0 text-emerald-600" aria-hidden="true" />
          ) : (
            <X className="mt-0.5 size-3 shrink-0 text-destructive" aria-hidden="true" />
          )}
          <span className="min-w-0">
            <span className="font-medium">{result.skill}</span>
            <span className="text-muted-foreground"> — {summarize(result)}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}
