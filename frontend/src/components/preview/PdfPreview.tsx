interface PdfPreviewProps {
  src: string
  filename: string
}

export function PdfPreview({ src, filename }: PdfPreviewProps) {
  return (
    <iframe
      src={src}
      title={filename}
      className="h-full w-full rounded border-0"
      aria-label={`PDF preview of ${filename}`}
    />
  )
}
