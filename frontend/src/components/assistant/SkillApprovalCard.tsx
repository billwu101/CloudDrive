import { Loader2, ShieldCheck, Sparkles, X } from 'lucide-react'

import type { AssistantSkillResponse } from '@/api/types'
import { Button } from '@/components/ui/button'

interface SkillApprovalCardProps {
  skill: AssistantSkillResponse
  loading: boolean
  onApprove: (skill: AssistantSkillResponse) => void
  onDismiss: () => void
}

export function SkillApprovalCard({
  skill,
  loading,
  onApprove,
  onDismiss,
}: SkillApprovalCardProps) {
  const actions = skill.manifest.ui.context_menu

  return (
    <article className="rounded-md border border-border bg-background p-3 shadow-sm">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Sparkles className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          <div>
            <p className="text-sm font-semibold">Skill proposal</p>
            <p className="text-xs text-muted-foreground">{skill.description}</p>
          </div>
          <div className="space-y-1 rounded-md bg-muted/60 p-2 text-xs">
            <p className="font-medium">{skill.manifest.name}</p>
            {actions.map((action) => (
              <p key={`${action.handler}:${action.label}`} className="text-muted-foreground">
                Adds "{action.label}" to {action.item_types.join(', ')}
              </p>
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onDismiss}
              disabled={loading}
            >
              <X className="size-3.5" aria-hidden="true" />
              Dismiss
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => onApprove(skill)}
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <ShieldCheck className="size-3.5" aria-hidden="true" />
              )}
              Approve
            </Button>
          </div>
        </div>
      </div>
    </article>
  )
}
