import { Loader2, Save, X } from 'lucide-react'
import { useState } from 'react'

import type { AssistantSkillResponse, AssistantSkillUpdateRequest } from '@/api/types'
import { Button } from '@/components/ui/button'

interface SkillEditDialogProps {
  skill: AssistantSkillResponse | null
  loading: boolean
  error?: string | null
  onSave: (skillId: string, body: AssistantSkillUpdateRequest) => void
  onClose: () => void
}

/**
 * Edit surface for an installed skill: the description (shown in the right-click
 * menu and review surfaces) and the generated code. Edited code is re-validated
 * server-side through codeguard before it is stored, so a manual edit cannot
 * bypass the static safety scan.
 */
export function SkillEditDialog({ skill, loading, error, onSave, onClose }: SkillEditDialogProps) {
  const [description, setDescription] = useState(skill?.description ?? '')
  const [code, setCode] = useState(skill?.code ?? '')

  if (!skill) return null

  const trimmedDescription = description.trim()
  const dirty = trimmedDescription !== skill.description || code !== skill.code
  const canSave = dirty && trimmedDescription.length > 0 && !loading

  const handleSave = () => {
    const body: AssistantSkillUpdateRequest = {}
    if (trimmedDescription !== skill.description) body.description = trimmedDescription
    if (code !== skill.code) body.code = code
    onSave(skill.id, body)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="skill-edit-title"
        className="flex max-h-[85vh] w-full max-w-lg flex-col rounded-lg border bg-popover p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id="skill-edit-title" className="text-sm font-semibold">
              Edit skill: {skill.name}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Changes apply to the installed skill immediately after saving.
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close editor"
            title="Close editor"
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>

        <label htmlFor="skill-edit-description" className="mb-1 text-xs font-medium">
          Description
        </label>
        <input
          id="skill-edit-description"
          type="text"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={500}
          className="mb-3 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
        />

        <label htmlFor="skill-edit-code" className="mb-1 text-xs font-medium">
          Code
        </label>
        <textarea
          id="skill-edit-code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          spellCheck={false}
          className="min-h-48 flex-1 resize-none overflow-auto rounded-md border border-input bg-muted/40 p-3 font-mono text-xs leading-relaxed outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
          aria-label="Skill code"
        />

        {error && (
          <p role="alert" className="mt-3 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </p>
        )}

        <p className="mt-3 text-xs text-muted-foreground">
          Edited code is re-validated and still runs only in the restricted sandbox (no network, no
          shell, writes confined to the output).
        </p>

        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button type="button" size="sm" onClick={handleSave} disabled={!canSave}>
            {loading ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <Save className="size-3.5" aria-hidden="true" />
            )}
            Save changes
          </Button>
        </div>
      </div>
    </div>
  )
}
