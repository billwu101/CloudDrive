import { File, Folder } from 'lucide-react'
import type { ReactNode } from 'react'

import type { DriveItemResponse, SemanticHitResponse } from '@/api/types'

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Highlight any query terms that happen to appear in the snippet. Semantic
 *  matches don't always contain the literal words, so this is best-effort. */
function highlight(snippet: string, query: string): ReactNode {
  const terms = query.trim().split(/\s+/).filter(Boolean).map(escapeRegExp)
  if (terms.length === 0) return snippet
  const re = new RegExp(`(${terms.join('|')})`, 'gi')
  const parts = snippet.split(re)
  return parts.map((part, i) =>
    re.test(part) ? (
      <mark key={i} className="rounded bg-yellow-200 px-0.5 dark:bg-yellow-500/40">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  )
}

function scorePercent(score: number): number {
  return Math.round(Math.max(0, Math.min(1, score)) * 100)
}

export function SemanticResultList({
  hits,
  query,
  onOpen,
}: {
  hits: SemanticHitResponse[]
  query: string
  onOpen: (item: DriveItemResponse) => void
}) {
  return (
    <ul className="flex flex-col gap-2">
      {hits.map(({ item, score, snippet }) => (
        <li key={item.id}>
          <button
            type="button"
            onClick={() => onOpen(item)}
            className="flex w-full flex-col gap-1 rounded-lg border border-border p-3 text-left transition-colors hover:bg-accent"
          >
            <div className="flex items-center gap-2">
              {item.item_type === 'FOLDER' ? (
                <Folder className="size-4 shrink-0 text-primary" aria-hidden="true" />
              ) : (
                <File className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              )}
              <span className="truncate text-sm font-medium">{item.name}</span>
              <span
                className="ml-auto shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
                title="Relevance"
              >
                {scorePercent(score)}% match
              </span>
            </div>
            {snippet && (
              <p className="line-clamp-2 text-xs text-muted-foreground">
                {highlight(snippet, query)}
              </p>
            )}
          </button>
        </li>
      ))}
    </ul>
  )
}
