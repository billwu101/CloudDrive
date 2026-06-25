import { Bookmark, ListChecks, Loader2, Play, ShieldAlert, X } from 'lucide-react'

import type { WorkflowPlanView } from '@/api/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface WorkflowPlanCardProps {
  plan: WorkflowPlanView
  loading: boolean
  onConfirm: (workflowId: string) => void
  onCancel: (workflowId: string) => void
  onSave?: (plan: WorkflowPlanView) => void
  saving?: boolean
}

export function WorkflowPlanCard({
  plan,
  loading,
  onConfirm,
  onCancel,
  onSave,
  saving,
}: WorkflowPlanCardProps) {
  const workflowId = plan.workflow_id
  if (workflowId === null) return null

  return (
    <article
      className="rounded-md border border-border bg-background p-3 shadow-sm"
      aria-label="Workflow plan"
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-amber-500/15 text-amber-600">
          <ListChecks className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          <div>
            <p className="text-sm font-semibold">Plan needs your confirmation</p>
            <p className="text-xs text-muted-foreground">
              Review the steps below. Nothing runs until you confirm.
            </p>
          </div>
          <ol className="space-y-1 rounded-md bg-muted/60 p-2 text-xs">
            {plan.steps.map((step) => (
              <li key={step.index} className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate font-medium">
                  {step.index + 1}. {step.skill}
                </span>
                <span
                  className={cn(
                    'inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
                    step.requires_approval
                      ? 'bg-destructive/10 text-destructive'
                      : 'bg-muted text-muted-foreground',
                  )}
                >
                  {step.requires_approval && <ShieldAlert className="size-3" aria-hidden="true" />}
                  {step.permission_tier}
                </span>
              </li>
            ))}
          </ol>
          <div className="flex justify-end gap-2">
            {onSave && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onSave(plan)}
                disabled={loading || saving}
                title="Save this workflow to re-run later"
              >
                <Bookmark className="size-3.5" aria-hidden="true" />
                Save
              </Button>
            )}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onCancel(workflowId)}
              disabled={loading}
            >
              <X className="size-3.5" aria-hidden="true" />
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => onConfirm(workflowId)}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Play className="size-3.5" aria-hidden="true" />
              )}
              Confirm &amp; run
            </Button>
          </div>
        </div>
      </div>
    </article>
  )
}
