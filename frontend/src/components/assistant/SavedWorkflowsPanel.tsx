import { Loader2, Play, Repeat2 } from 'lucide-react'

import type { AssistantSavedWorkflowResponse } from '@/api/types'
import { Button } from '@/components/ui/button'

interface SavedWorkflowsPanelProps {
  workflows: AssistantSavedWorkflowResponse[]
  rerunningId: string | null
  onRerun: (workflowId: string) => void
}

/**
 * Compact list of the user's saved workflows with one-click re-run.
 */
export function SavedWorkflowsPanel({
  workflows,
  rerunningId,
  onRerun,
}: SavedWorkflowsPanelProps) {
  if (workflows.length === 0) return null

  return (
    <section
      className="rounded-md border border-border bg-background p-3 shadow-sm"
      aria-label="Saved workflows"
    >
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <Repeat2 className="size-4 text-primary" aria-hidden="true" />
        Saved workflows
      </div>
      <ul className="space-y-1">
        {workflows.map((workflow) => {
          const rerunning = rerunningId === workflow.id
          return (
            <li
              key={workflow.id}
              className="flex items-center justify-between gap-2 rounded-md bg-muted/50 px-2 py-1.5"
            >
              <div className="min-w-0">
                <p className="truncate text-xs font-medium">{workflow.name}</p>
                <p className="text-[10px] text-muted-foreground">
                  {workflow.steps.length} step{workflow.steps.length === 1 ? '' : 's'}
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => onRerun(workflow.id)}
                disabled={rerunning}
                title={`Re-run "${workflow.name}"`}
              >
                {rerunning ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <Play className="size-3.5" aria-hidden="true" />
                )}
                Run
              </Button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
