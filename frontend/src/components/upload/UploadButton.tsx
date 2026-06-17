import { Upload } from 'lucide-react'
import { useEffect, useRef } from 'react'

interface UploadButtonProps {
  onFiles: (files: File[]) => void
  /** When true, the picker selects a whole folder (preserving its structure). */
  directory?: boolean
  className?: string
  children?: React.ReactNode
}

export function UploadButton({
  onFiles,
  directory = false,
  className,
  children,
}: UploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  // `webkitdirectory` is non-standard, so set it imperatively (not a JSX attr).
  useEffect(() => {
    const input = inputRef.current
    if (!input) return
    if (directory) {
      input.setAttribute('webkitdirectory', '')
      input.setAttribute('directory', '')
    } else {
      input.removeAttribute('webkitdirectory')
      input.removeAttribute('directory')
    }
  }, [directory])

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
