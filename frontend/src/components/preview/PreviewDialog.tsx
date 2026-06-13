import { Download, Loader2, X } from 'lucide-react'
import { useEffect } from 'react'

import { getContentUrl } from '@/api/previewApi'
import { usePreviewInfo } from '@/hooks/usePreview'

import { AudioPreview } from './AudioPreview'
import { ImagePreview } from './ImagePreview'
import { PdfPreview } from './PdfPreview'
import { TextPreview } from './TextPreview'
import { UnsupportedPreview } from './UnsupportedPreview'
import { VideoPreview } from './VideoPreview'

interface PreviewDialogProps {
  itemId: string | null
  onClose: () => void
}

function PreviewContent({ itemId }: { itemId: string }) {
  const { data, isLoading, isError } = usePreviewInfo(itemId)
  const contentUrl = getContentUrl(itemId)

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" aria-label="Loading preview" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-destructive">Failed to load preview.</p>
      </div>
    )
  }

  switch (data.preview_type) {
    case 'image':
      return <ImagePreview src={contentUrl} filename={data.filename} />
    case 'pdf':
      return <PdfPreview src={contentUrl} filename={data.filename} />
    case 'text':
      return <TextPreview src={contentUrl} />
    case 'video':
      return <VideoPreview src={contentUrl} mimeType={data.mime_type} />
    case 'audio':
      return <AudioPreview src={contentUrl} filename={data.filename} mimeType={data.mime_type} />
    default:
      return (
        <UnsupportedPreview
          filename={data.filename}
          mimeType={data.mime_type}
          downloadUrl={contentUrl}
        />
      )
  }
}

export function PreviewDialog({ itemId, onClose }: PreviewDialogProps) {
  const { data } = usePreviewInfo(itemId)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  if (!itemId) return null

  const contentUrl = itemId ? getContentUrl(itemId) : null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={data?.filename ?? 'File preview'}
      className="fixed inset-0 z-50 flex flex-col bg-black/80"
      onClick={onClose}
    >
      {/* Toolbar */}
      <div
        className="flex h-14 shrink-0 items-center justify-between gap-4 bg-black/60 px-4"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="truncate text-sm font-medium text-white">
          {data?.filename ?? ''}
        </span>
        <div className="flex items-center gap-2">
          {contentUrl && (
            <a
              href={contentUrl}
              download={data?.filename}
              aria-label="Download file"
              className="flex size-8 items-center justify-center rounded text-white/70 transition-colors hover:bg-white/10 hover:text-white"
            >
              <Download className="size-5" aria-hidden="true" />
            </a>
          )}
          <button
            aria-label="Close preview"
            onClick={onClose}
            className="flex size-8 items-center justify-center rounded text-white/70 transition-colors hover:bg-white/10 hover:text-white"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div
        className="min-h-0 flex-1 overflow-auto bg-background"
        onClick={(e) => e.stopPropagation()}
      >
        <PreviewContent itemId={itemId} />
      </div>
    </div>
  )
}
