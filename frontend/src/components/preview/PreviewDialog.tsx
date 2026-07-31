import { Download, Loader2, X } from 'lucide-react'
import { useEffect } from 'react'

import { downloadItem } from '@/api/download'
import type { PreviewInfoResponse } from '@/api/types'
import { usePreviewBlobUrl, usePreviewInfo } from '@/hooks/usePreview'

import { AudioPreview } from './AudioPreview'
import { ImagePreview } from './ImagePreview'
import { MarkdownPreview } from './MarkdownPreview'
import { PdfPreview } from './PdfPreview'
import { TextPreview } from './TextPreview'
import { UnsupportedPreview } from './UnsupportedPreview'
import { VideoPreview } from './VideoPreview'

/**
 * Where the dialog gets its data — swapped out on the guest side, which reads
 * the `/public` endpoints with a share credential instead of the user's token.
 * The three pieces are separate because a guest has no `/preview/{id}` info
 * endpoint at all: the type already came down with the folder listing.
 */
export interface PreviewSource {
  useInfo: (itemId: string | null) => {
    data: PreviewInfoResponse | undefined
    isLoading: boolean
    isError: boolean
  }
  useBlobUrl: (itemId: string | null, converted: boolean) => { url: string | null; isError: boolean }
  download: (itemId: string, filename: string) => void
}

const driveSource: PreviewSource = {
  useInfo: usePreviewInfo,
  useBlobUrl: usePreviewBlobUrl,
  download: downloadItem,
}

interface PreviewDialogProps {
  itemId: string | null
  onClose: () => void
  /** Defaults to the signed-in drive endpoints. */
  source?: PreviewSource
}

function PreviewContent({ itemId, source }: { itemId: string; source: PreviewSource }) {
  const { data, isLoading, isError } = source.useInfo(itemId)
  // Office documents need the PDF-converted endpoint; everything else the raw file.
  const converted = data?.preview_type === 'document'
  const needsContent = !!data && data.preview_type !== 'unsupported'
  const { url: blobUrl, isError: blobError } = source.useBlobUrl(
    needsContent ? itemId : null,
    converted,
  )

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

  if (data.preview_type === 'unsupported') {
    return (
      <UnsupportedPreview
        filename={data.filename}
        mimeType={data.mime_type}
        onDownload={() => source.download(itemId, data.filename)}
      />
    )
  }

  if (blobError) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-destructive">Failed to load preview content.</p>
      </div>
    )
  }

  if (blobUrl === null) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" aria-label="Loading preview" />
      </div>
    )
  }

  switch (data.preview_type) {
    case 'image':
      return <ImagePreview src={blobUrl} filename={data.filename} />
    case 'pdf':
    case 'document':
      return <PdfPreview src={blobUrl} filename={data.filename} />
    case 'text':
      return <TextPreview src={blobUrl} />
    case 'markdown':
      return <MarkdownPreview src={blobUrl} />
    case 'video':
      return <VideoPreview src={blobUrl} mimeType={data.mime_type} />
    case 'audio':
      return <AudioPreview src={blobUrl} filename={data.filename} mimeType={data.mime_type} />
    default:
      return (
        <UnsupportedPreview
          filename={data.filename}
          mimeType={data.mime_type}
          onDownload={() => source.download(itemId, data.filename)}
        />
      )
  }
}

export function PreviewDialog({ itemId, onClose, source = driveSource }: PreviewDialogProps) {
  const { data } = source.useInfo(itemId)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  if (!itemId) return null

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
          {data && (
            <button
              onClick={() => source.download(itemId, data.filename)}
              aria-label="Download file"
              className="flex size-8 items-center justify-center rounded text-white/70 transition-colors hover:bg-white/10 hover:text-white"
            >
              <Download className="size-5" aria-hidden="true" />
            </button>
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
        <PreviewContent itemId={itemId} source={source} />
      </div>
    </div>
  )
}
