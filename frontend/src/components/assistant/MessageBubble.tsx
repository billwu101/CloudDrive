import { Bot, User } from 'lucide-react'

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

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const Icon = isUser ? User : Bot

  return (
    <div className={cn('flex gap-2', isUser && 'justify-end')}>
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
