import { Upload } from 'lucide-react'
import { useRef } from 'react'

interface UploadButtonProps {
  onFiles: (files: File[]) => void
  className?: string
  children?: React.ReactNode
}

export function UploadButton({ onFiles, className, children }: UploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    if (files.length > 0) {
      onFiles(files)
      e.target.value = ''
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        aria-hidden="true"
        onChange={handleChange}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className={
          className ??
          'flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
        }
      >
        {children ?? (
          <>
            <Upload className="size-4" aria-hidden="true" />
            Upload
          </>
        )}
      </button>
    </>
  )
}
