import { AlertTriangle, Loader2, Pencil, Sparkles, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { isApiError } from '@/api/client'
import type { AssistantSkillResponse, AssistantSkillUpdateRequest } from '@/api/types'
import { SkillEditDialog } from '@/components/assistant/SkillEditDialog'
import { Button } from '@/components/ui/button'
import {
  useAssistantSkills,
  useDeleteAssistantSkill,
  useUpdateAssistantSkill,
} from '@/hooks/useAssistant'

function formatDate(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

interface SkillCardProps {
  skill: AssistantSkillResponse
  onEdit: (skill: AssistantSkillResponse) => void
  onDelete: (skill: AssistantSkillResponse) => void
}

function SkillCard({ skill, onEdit, onDelete }: SkillCardProps) {
  const actions = skill.manifest.ui?.context_menu ?? []
  return (
    <li className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 shrink-0 text-primary" aria-hidden="true" />
            <h3 className="truncate font-medium text-sm">{skill.name}</h3>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{skill.description}</p>
          {actions.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {actions.map((action) => (
                <span
                  key={`${action.handler}:${action.label}`}
                  className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                >
                  Right-click: {action.label}
                </span>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-muted-foreground">Updated {formatDate(skill.updated_at)}</p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onEdit(skill)}
            aria-label={`Edit ${skill.name}`}
          >
            <Pencil className="size-3.5" aria-hidden="true" />
            Edit
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => onDelete(skill)}
            aria-label={`Delete ${skill.name}`}
          >
            <Trash2 className="size-3.5" aria-hidden="true" />
            Delete
          </Button>
        </div>
      </div>
    </li>
  )
}

export function SkillsPage() {
  const { data: skills, isLoading, isError } = useAssistantSkills('installed')
  const updateSkill = useUpdateAssistantSkill()
  const deleteSkill = useDeleteAssistantSkill()

  const [editing, setEditing] = useState<AssistantSkillResponse | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<AssistantSkillResponse | null>(null)

  const handleSave = async (skillId: string, body: AssistantSkillUpdateRequest) => {
    setEditError(null)
    try {
      await updateSkill.mutateAsync({ skillId, body })
      setEditing(null)
    } catch (err) {
      setEditError(isApiError(err) ? err.message : 'Failed to save changes.')
    }
  }

  const handleDelete = async () => {
    if (!deleting) return
    try {
      await deleteSkill.mutateAsync(deleting.id)
      setDeleting(null)
    } catch {
      // Keep the dialog open; the list refetch on success is the success signal.
    }
  }

  const count = skills?.length ?? 0

  return (
    <div className="mx-auto max-w-3xl px-1 py-4 sm:px-4 sm:py-8">
      <header className="mb-7">
        <div className="mb-3 flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <Sparkles className="size-6" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Skills</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {isLoading
            ? 'Loading your installed skills…'
            : count === 0
              ? 'No skills installed yet. Ask the assistant to build one.'
              : `${count} skill${count === 1 ? '' : 's'} installed. Edit or remove the ones you no longer need.`}
        </p>
      </header>

      {isError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          Skills could not be loaded. Please refresh the page and try again.
        </div>
      )}

      {isLoading && (
        <div className="flex min-h-40 items-center justify-center text-muted-foreground">
          <Loader2 className="mr-2 size-5 animate-spin" aria-hidden="true" />
          Loading…
        </div>
      )}

      {!isLoading && !isError && count === 0 && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border py-16 text-muted-foreground">
          <Sparkles className="size-12" aria-hidden="true" />
          <p className="text-sm">No installed skills</p>
        </div>
      )}

      {!isLoading && count > 0 && (
        <ul className="space-y-3">
          {skills?.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              onEdit={(s) => {
                setEditError(null)
                setEditing(s)
              }}
              onDelete={(s) => setDeleting(s)}
            />
          ))}
        </ul>
      )}

      {editing && (
        <SkillEditDialog
          key={editing.id}
          skill={editing}
          loading={updateSkill.isPending}
          error={editError}
          onSave={(skillId, body) => void handleSave(skillId, body)}
          onClose={() => setEditing(null)}
        />
      )}

      {deleting && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setDeleting(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="skill-delete-title"
            className="w-full max-w-sm rounded-lg border bg-popover p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start gap-3">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
                <AlertTriangle className="size-5 text-destructive" aria-hidden="true" />
              </div>
              <div>
                <h2 id="skill-delete-title" className="text-sm font-semibold">
                  Delete skill?
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  "{deleting.name}" and its right-click action will be removed. This cannot be undone.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setDeleting(null)}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => void handleDelete()}
                disabled={deleteSkill.isPending}
              >
                {deleteSkill.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <Trash2 className="size-3.5" aria-hidden="true" />
                )}
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
