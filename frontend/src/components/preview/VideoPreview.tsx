interface VideoPreviewProps {
  src: string
  mimeType?: string | null
}

export function VideoPreview({ src, mimeType }: VideoPreviewProps) {
  return (
    <div className="flex h-full items-center justify-center bg-black p-4">
      <video
        controls
        className="max-h-full max-w-full rounded"
        aria-label="Video preview"
      >
        <source src={src} type={mimeType ?? undefined} />
        Your browser does not support video playback.
      </video>
    </div>
  )
}
