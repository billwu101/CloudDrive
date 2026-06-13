import { useEffect, useState } from 'react'

interface TextPreviewInnerProps {
  src: string
}

function TextPreviewInner({ src }: TextPreviewInnerProps) {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch(src, { credentials: 'include' })
      .then((r) => r.text())
      .then((t) => { if (!cancelled) setContent(t) })
      .catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [src])

  if (error) return <p className="p-4 text-sm text-destructive">Failed to load text content.</p>
  if (content === null) return <p className="p-4 text-sm text-muted-foreground">Loading…</p>

  return (
    <pre className="h-full w-full overflow-auto whitespace-pre-wrap break-words p-4 font-mono text-sm text-foreground">
      {content}
    </pre>
  )
}

export function TextPreview({ src }: TextPreviewInnerProps) {
  // key forces full remount when src changes, avoiding setState-in-effect
  return <TextPreviewInner key={src} src={src} />
}
