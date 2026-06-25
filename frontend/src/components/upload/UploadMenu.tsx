import { ChevronDown, File, FolderUp, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

interface UploadMenuProps {
  onFiles: (files: File[]) => void
  onFolders: (files: File[]) => void
}

/** A single "Upload" button that opens a menu to upload either files or a whole
 *  folder (the folder picker uses the non-standard webkitdirectory attribute). */
export function UploadMenu({ onFiles, onFolders }: UploadMenuProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)

  // The folder picker needs webkitdirectory, which isn't a standard JSX attr.
  useEffect(() => {
    const input = folderInputRef.current
    if (input) {
      input.setAttribute('webkitdirectory', '')
      input.setAttribute('directory', '')
    }
  }, [])

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return
    const onPointer = (e: PointerEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('pointerdown', onPointer)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', onPointer)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  const pick = (ref: React.RefObject<HTMLInputElement | null>) => {
    setOpen(false)
    ref.current?.click()
  }

  const handleChange =
    (handler: (files: File[]) => void) => (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? [])
      if (files.length > 0) handler(files)
      e.target.value = ''
    }

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        aria-hidden="true"
        onChange={handleChange(onFiles)}
      />
      <input
        ref={folderInputRef}
        type="file"
        multiple
        className="hidden"
        aria-hidden="true"
        onChange={handleChange(onFolders)}
      />

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Upload className="size-4" aria-hidden="true" />
        Upload
        <ChevronDown className="size-3.5" aria-hidden="true" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-1 w-44 overflow-hidden rounded-md border border-border bg-popover py-1 shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => pick(fileInputRef)}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-popover-foreground transition-colors hover:bg-accent"
          >
            <File className="size-4" aria-hidden="true" />
            Upload files
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => pick(folderInputRef)}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-popover-foreground transition-colors hover:bg-accent"
          >
            <FolderUp className="size-4" aria-hidden="true" />
            Upload folder
          </button>
        </div>
      )}
    </div>
  )
}
