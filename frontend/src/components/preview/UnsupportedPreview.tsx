import { FileX } from 'lucide-react'

interface UnsupportedPreviewProps {
  filename: string
  mimeType?: string | null
  downloadUrl: string
}

export function UnsupportedPreview({ filename, mimeType, downloadUrl }: UnsupportedPreviewProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
      <FileX className="size-14 text-muted-foreground" aria-hidden="true" />
      <div>
        <p className="font-medium">{filename}</p>
        {mimeType && (
          <p className="mt-1 text-sm text-muted-foreground">{mimeType}</p>
        )}
        <p className="mt-2 text-sm text-muted-foreground">
          Preview not available for this file type.
        </p>
      </div>
      <a
        href={downloadUrl}
        download={filename}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/80"
      >
        Download file
      </a>
    </div>
  )
}
