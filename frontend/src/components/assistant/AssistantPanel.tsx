import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Bot, Loader2, MessageSquareText, Send, X } from 'lucide-react'

import type { AssistantSkillResponse, ModelTarget, WorkflowPlanView } from '@/api/types'
import { Button } from '@/components/ui/button'
import { isApiError } from '@/api/client'
import {
  useApproveAssistantSkill,
  useAssistantChatMutation,
  useAssistantModels,
  useCancelWorkflow,
  useConfirmWorkflow,
  useRerunWorkflow,
  useSaveWorkflow,
  useSavedWorkflows,
} from '@/hooks/useAssistant'
import { cn } from '@/lib/utils'
import { MessageBubble, type AssistantMessage } from './MessageBubble'
import { SavedWorkflowsPanel } from './SavedWorkflowsPanel'
import { SkillApprovalCard } from './SkillApprovalCard'
import { SkillApprovalDialog } from './SkillApprovalDialog'
import { WorkflowPlanCard } from './WorkflowPlanCard'

const INITIAL_MESSAGE: AssistantMessage = {
  id: 'assistant-welcome',
  role: 'assistant',
  content: 'Hi. What would you like to do in CloudDrive?',
}

function newMessageId(role: AssistantMessage['role']) {
  return `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function errorMessage(error: unknown) {
  if (isApiError(error)) {
    // The backend returns a model-specific reason (offline / credential / quota);
    // show it directly so the user knows which model failed and why.
    return error.message || 'Assistant is unavailable right now.'
  }
  return 'Assistant could not complete that request.'
}

export function AssistantPanel() {
  const [isOpen, setIsOpen] = useState(false)
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [messages, setMessages] = useState<AssistantMessage[]>([INITIAL_MESSAGE])
  const [pendingSkill, setPendingSkill] = useState<AssistantSkillResponse | null>(null)
  const [pendingPlan, setPendingPlan] = useState<WorkflowPlanView | null>(null)
  const [reviewingSkill, setReviewingSkill] = useState(false)
  const [lastPrompt, setLastPrompt] = useState('')
  const [selectedModel, setSelectedModel] = useState<ModelTarget | undefined>()
  const models = useAssistantModels()
  const chatMutation = useAssistantChatMutation()
  const approveSkill = useApproveAssistantSkill()
  const confirmWorkflow = useConfirmWorkflow()
  const cancelWorkflow = useCancelWorkflow()
  const savedWorkflows = useSavedWorkflows()
  const saveWorkflow = useSaveWorkflow()
  const rerunWorkflow = useRerunWorkflow()
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!isOpen) return
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [isOpen, messages, chatMutation.isPending])

  // Default the picker once models load: prefer a configured external model
  // (local may be offline), otherwise fall back to local.
  useEffect(() => {
    if (selectedModel || !models.data) return
    const opts = models.data
    const preferred =
      opts.find((m) => m.available && m.id !== 'local') ?? opts.find((m) => m.available)
    if (preferred) setSelectedModel(preferred.id)
  }, [models.data, selectedModel])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const message = input.trim()
    if (!message || chatMutation.isPending) return

    setInput('')
    setLastPrompt(message)
    setMessages((current) => [
      ...current,
      { id: newMessageId('user'), role: 'user', content: message },
    ])

    try {
      const response = await chatMutation.mutateAsync({
        message,
        session_id: sessionId,
        model: selectedModel,
      })
      setSessionId(response.session_id)
      setPendingSkill(response.skill_proposal ?? null)
      setPendingPlan(
        response.plan && response.plan.status === 'pending_approval' ? response.plan : null,
      )
      setMessages((current) => [
        ...current,
        {
          id: newMessageId('assistant'),
          role: 'assistant',
          content: response.message,
          results: response.results?.length ? response.results : undefined,
        },
      ])
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: newMessageId('assistant'),
          role: 'assistant',
          content: errorMessage(error),
          status: 'error',
        },
      ])
    }
  }

  const handleApproveSkill = async (skill: AssistantSkillResponse) => {
    try {
      const response = await approveSkill.mutateAsync(skill.id)
      setPendingSkill(null)
      setMessages((current) => [
        ...current,
        {
          id: newMessageId('assistant'),
          role: 'assistant',
          content: `Installed ${response.skill.manifest.ui.context_menu[0]?.label ?? skill.name}.`,
        },
      ])
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: newMessageId('assistant'),
          role: 'assistant',
          content: errorMessage(error),
          status: 'error',
        },
      ])
    }
  }

  const appendAssistant = (
    content: string,
    status?: AssistantMessage['status'],
    results?: AssistantMessage['results'],
  ) => {
    setMessages((current) => [
      ...current,
      {
        id: newMessageId('assistant'),
        role: 'assistant',
        content,
        status,
        results: results && results.length > 0 ? results : undefined,
      },
    ])
  }

  const handleConfirmWorkflow = async (workflowId: string) => {
    try {
      const response = await confirmWorkflow.mutateAsync(workflowId)
      setPendingPlan(null)
      const results = response.results ?? []
      const failed = results.filter((result) => !result.ok)
      appendAssistant(
        failed.length === 0
          ? 'Done — the plan ran successfully.'
          : `Ran with ${failed.length} failed step(s).`,
        undefined,
        results,
      )
    } catch (error) {
      appendAssistant(errorMessage(error), 'error')
    }
  }

  const handleCancelWorkflow = async (workflowId: string) => {
    try {
      await cancelWorkflow.mutateAsync(workflowId)
      setPendingPlan(null)
      appendAssistant('Cancelled. Nothing was changed.')
    } catch (error) {
      appendAssistant(errorMessage(error), 'error')
    }
  }

  const handleSaveWorkflow = async (plan: WorkflowPlanView) => {
    const name = (lastPrompt || 'Saved workflow').slice(0, 80)
    try {
      await saveWorkflow.mutateAsync({
        name,
        source_nl: lastPrompt,
        steps: plan.steps.map((step) => ({
          skill: step.skill,
          arguments: step.arguments,
          depends_on: step.depends_on,
        })),
      })
      appendAssistant(`Saved this workflow as "${name}". You can re-run it any time.`)
    } catch (error) {
      appendAssistant(errorMessage(error), 'error')
    }
  }

  const handleRerunWorkflow = async (workflowId: string) => {
    try {
      const response = await rerunWorkflow.mutateAsync(workflowId)
      const results = response.results ?? []
      const failed = results.filter((result) => !result.ok)
      appendAssistant(
        failed.length === 0
          ? 'Re-ran the saved workflow successfully.'
          : `Re-ran with ${failed.length} failed step(s).`,
        undefined,
        results,
      )
    } catch (error) {
      appendAssistant(errorMessage(error), 'error')
    }
  }

  return (
    <div className="fixed bottom-4 right-4 z-40 flex flex-col items-end gap-3">
      {isOpen && (
        <section
          className={cn(
            'flex h-[min(560px,calc(100vh-6rem))] w-[min(420px,calc(100vw-2rem))] flex-col overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-xl',
          )}
          aria-label="CloudDrive assistant"
        >
          <header className="flex h-12 shrink-0 items-center justify-between border-b border-border px-3">
            <div className="flex min-w-0 items-center gap-2">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <Bot className="size-4" aria-hidden="true" />
              </span>
              <h2 className="truncate text-sm font-semibold">CloudDrive Assistant</h2>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => setIsOpen(false)}
              aria-label="Close assistant"
              title="Close assistant"
            >
              <X className="size-4" aria-hidden="true" />
            </Button>
          </header>

          <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto bg-muted/30 p-3">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {pendingSkill && (
              <SkillApprovalCard
                skill={pendingSkill}
                loading={approveSkill.isPending}
                onApprove={handleApproveSkill}
                onReview={() => setReviewingSkill(true)}
                onDismiss={() => setPendingSkill(null)}
              />
            )}
            {pendingPlan && (
              <WorkflowPlanCard
                plan={pendingPlan}
                loading={confirmWorkflow.isPending || cancelWorkflow.isPending}
                onConfirm={handleConfirmWorkflow}
                onCancel={handleCancelWorkflow}
                onSave={handleSaveWorkflow}
                saving={saveWorkflow.isPending}
              />
            )}
            <SavedWorkflowsPanel
              workflows={savedWorkflows.data ?? []}
              rerunningId={rerunWorkflow.isPending ? (rerunWorkflow.variables ?? null) : null}
              onRerun={handleRerunWorkflow}
            />
            {chatMutation.isPending && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                <span>Thinking</span>
              </div>
            )}
          </div>

          <form className="flex shrink-0 flex-col gap-2 border-t border-border p-3" onSubmit={handleSubmit}>
            <select
              value={selectedModel ?? ''}
              onChange={(event) => setSelectedModel(event.target.value as ModelTarget)}
              className="self-start rounded-md border border-input bg-background px-2 py-1 text-xs text-muted-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
              aria-label="Choose model"
              title="Choose which model answers"
            >
              {(models.data ?? []).map((option) => (
                <option key={option.id} value={option.id} disabled={!option.available}>
                  {option.label}
                  {option.available ? '' : ' (not configured)'}
                </option>
              ))}
            </select>
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                className="max-h-28 min-h-10 flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30"
                placeholder="Message assistant (press the send button)"
                aria-label="Assistant message"
                rows={1}
              />
              <Button
                type="submit"
                size="icon"
                disabled={!input.trim() || !selectedModel || chatMutation.isPending}
                aria-label="Send message"
                title="Send message"
              >
                {chatMutation.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Send className="size-4" aria-hidden="true" />
                )}
              </Button>
            </div>
          </form>

          {reviewingSkill && (
            <SkillApprovalDialog
              skill={pendingSkill}
              loading={approveSkill.isPending}
              onApprove={(skill) => {
                setReviewingSkill(false)
                void handleApproveSkill(skill)
              }}
              onReject={() => {
                setReviewingSkill(false)
                setPendingSkill(null)
              }}
              onClose={() => setReviewingSkill(false)}
            />
          )}
        </section>
      )}

      <Button
        type="button"
        size="icon-lg"
        className="size-11 rounded-full shadow-lg"
        onClick={() => setIsOpen((open) => !open)}
        aria-label={isOpen ? 'Hide assistant' : 'Open assistant'}
        aria-expanded={isOpen}
        title={isOpen ? 'Hide assistant' : 'Open assistant'}
      >
        <MessageSquareText className="size-5" aria-hidden="true" />
      </Button>
    </div>
  )
}
