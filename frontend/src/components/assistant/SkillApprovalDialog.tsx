import { Loader2, ShieldCheck, X } from 'lucide-react'

import type { AssistantSkillResponse } from '@/api/types'
import { Button } from '@/components/ui/button'

interface SkillApprovalDialogProps {
  skill: AssistantSkillResponse | null
  loading: boolean
  onApprove: (skill: AssistantSkillResponse) => void
  onReject: () => void
  onClose: () => void
}

/**
 * Full review surface for a generated skill before it is installed: shows the
 * complete generated code and the right-click actions it would add, so the user
 * makes an informed approve/reject decision (the code only ever runs in the
 * sandbox after approval).
 */
export function SkillApprovalDialog({
  skill,
  loading,
  onApprove,
  onReject,
  onClose,
}: SkillApprovalDialogProps) {
  if (!skill) return null
  const actions = skill.manifest.ui.context_menu

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="skill-approval-title"
        className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-lg border bg-popover p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id="skill-approval-title" className="text-sm font-semibold">
              Review generated skill: {skill.name}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">{skill.description}</p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close review"
            title="Close review"
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>

        {actions.length > 0 && (
          <div className="mb-3 space-y-1 rounded-md bg-muted/60 p-2 text-xs">
            {actions.map((action) => (
              <p key={`${action.handler}:${action.label}`} className="text-muted-foreground">
                Adds "{action.label}" to {action.item_types.join(', ')}
              </p>
            ))}
          </div>
        )}

        <p className="mb-1 text-xs font-medium text-muted-foreground">Generated code</p>
        <pre
          className="min-h-0 flex-1 overflow-auto rounded-md border bg-muted/40 p-3 text-xs leading-relaxed"
          aria-label="Generated skill code"
        >
          <code>{skill.code}</code>
        </pre>

        <p className="mt-3 text-xs text-muted-foreground">
          This code runs only in a restricted sandbox (no network, no shell, writes confined to the
          output) and only after you approve it.
        </p>

        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onReject} disabled={loading}>
            <X className="size-3.5" aria-hidden="true" />
            Reject
          </Button>
          <Button type="button" size="sm" onClick={() => onApprove(skill)} disabled={loading}>
            {loading ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <ShieldCheck className="size-3.5" aria-hidden="true" />
            )}
            Approve &amp; install
          </Button>
        </div>
      </div>
    </div>
  )
}
