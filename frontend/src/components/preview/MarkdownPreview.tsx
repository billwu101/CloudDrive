import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface MarkdownPreviewProps {
  src: string
}

function MarkdownPreviewInner({ src }: MarkdownPreviewProps) {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch(src, { credentials: 'include' })
      .then((r) => r.text())
      .then((t) => {
        if (!cancelled) setContent(t)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
    }
  }, [src])

  if (error)
    return <p className="p-4 text-sm text-destructive">Failed to load markdown content.</p>
  if (content === null)
    return <p className="p-4 text-sm text-muted-foreground">Loading…</p>

  return (
    <div className="prose prose-sm dark:prose-invert mx-auto max-w-3xl break-words p-6 text-foreground">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}

export function MarkdownPreview({ src }: MarkdownPreviewProps) {
  // key forces a full remount when src changes (mirrors TextPreview).
  return <MarkdownPreviewInner key={src} src={src} />
}
