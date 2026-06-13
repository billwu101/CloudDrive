interface AudioPreviewProps {
  src: string
  filename: string
  mimeType?: string | null
}

export function AudioPreview({ src, filename, mimeType }: AudioPreviewProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
      <p className="text-sm font-medium">{filename}</p>
      <audio controls className="w-full max-w-sm" aria-label={`Audio preview of ${filename}`}>
        <source src={src} type={mimeType ?? undefined} />
        Your browser does not support audio playback.
      </audio>
    </div>
  )
}
