import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Bot, Loader2, MessageSquareText, Send, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { isApiError } from '@/api/client'
import { useAssistantChatMutation } from '@/hooks/useAssistant'
import { cn } from '@/lib/utils'
import { MessageBubble, type AssistantMessage } from './MessageBubble'

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
    if (error.code === 'ASSISTANT_UNAVAILABLE') {
      return 'Assistant is unavailable right now.'
    }
    return error.message
  }
  return 'Assistant could not complete that request.'
}

export function AssistantPanel() {
  const [isOpen, setIsOpen] = useState(false)
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [messages, setMessages] = useState<AssistantMessage[]>([INITIAL_MESSAGE])
  const chatMutation = useAssistantChatMutation()
  const listRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!isOpen) return
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [isOpen, messages, chatMutation.isPending])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const message = input.trim()
    if (!message || chatMutation.isPending) return

    setInput('')
    setMessages((current) => [
      ...current,
      { id: newMessageId('user'), role: 'user', content: message },
    ])

    try {
      const response = await chatMutation.mutateAsync({
        message,
        session_id: sessionId,
      })
      setSessionId(response.session_id)
      setMessages((current) => [
        ...current,
        { id: newMessageId('assistant'), role: 'assistant', content: response.message },
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
            {chatMutation.isPending && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                <span>Thinking</span>
              </div>
            )}
          </div>

          <form className="flex shrink-0 items-end gap-2 border-t border-border p-3" onSubmit={handleSubmit}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
              className="max-h-28 min-h-10 flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30"
              placeholder="Message assistant"
              aria-label="Assistant message"
              rows={1}
            />
            <Button
              type="submit"
              size="icon"
              disabled={!input.trim() || chatMutation.isPending}
              aria-label="Send message"
              title="Send message"
            >
              {chatMutation.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="size-4" aria-hidden="true" />
              )}
            </Button>
          </form>
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
