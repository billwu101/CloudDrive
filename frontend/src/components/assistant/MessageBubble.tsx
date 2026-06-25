import { Bot, Check, Copy, User } from 'lucide-react'
import { useState } from 'react'

import type { WorkflowStepResult } from '@/api/types'
import { cn } from '@/lib/utils'
import { StepResultList } from './StepResultList'

export interface AssistantMessage {
  id: string
  role: 'assistant' | 'user'
  content: string
  status?: 'normal' | 'error'
  results?: WorkflowStepResult[]
}

interface MessageBubbleProps {
  message: AssistantMessage
}

/**
 * Copy-to-clipboard control shown only next to user messages — the assistant's
 * replies are intentionally not copyable here, only what the human asked.
 */
function CopyMessageButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard unavailable (e.g. insecure context) — fail silently.
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? 'Copied' : 'Copy message'}
      title={copied ? 'Copied' : 'Copy message'}
      className={cn(
        'mt-0.5 flex size-6 shrink-0 items-center justify-center self-center rounded-md text-muted-foreground',
        'opacity-0 transition-colors transition-opacity hover:bg-muted hover:text-foreground',
        'group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
      )}
    >
      {copied ? (
        <Check className="size-3.5 text-emerald-600" aria-hidden="true" />
      ) : (
        <Copy className="size-3.5" aria-hidden="true" />
      )}
    </button>
  )
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const Icon = isUser ? User : Bot

  return (
    <div className={cn('group flex gap-2', isUser && 'justify-end')}>
      {isUser && <CopyMessageButton content={message.content} />}
      {!isUser && (
        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="size-3.5" aria-hidden="true" />
        </span>
      )}
      <div
        className={cn(
          'max-w-[82%] whitespace-pre-wrap rounded-md px-3 py-2 text-sm leading-5 shadow-sm',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'border border-border bg-background text-foreground',
          message.status === 'error' && 'border-destructive/30 bg-destructive/10 text-destructive',
        )}
      >
        {message.content}
        {!isUser && message.results && message.results.length > 0 && (
          <StepResultList results={message.results} />
        )}
      </div>
      {isUser && (
        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Icon className="size-3.5" aria-hidden="true" />
        </span>
      )}
    </div>
  )
}
