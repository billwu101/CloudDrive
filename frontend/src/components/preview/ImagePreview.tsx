interface ImagePreviewProps {
  src: string
  filename: string
}

export function ImagePreview({ src, filename }: ImagePreviewProps) {
  return (
    <div className="flex h-full items-center justify-center p-4">
      <img
        src={src}
        alt={filename}
        className="max-h-full max-w-full rounded object-contain shadow"
      />
    </div>
  )
}
