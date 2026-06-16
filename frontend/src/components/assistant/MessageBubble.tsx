import { Bot, User } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface AssistantMessage {
  id: string
  role: 'assistant' | 'user'
  content: string
  status?: 'normal' | 'error'
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
      </div>
      {isUser && (
        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Icon className="size-3.5" aria-hidden="true" />
        </span>
      )}
    </div>
  )
}
