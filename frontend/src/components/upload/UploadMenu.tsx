import { Upload } from 'lucide-react'
import { useRef } from 'react'

interface UploadMenuProps {
  onFiles: (files: File[]) => void
}

/** A single "Upload" button that opens the multi-file picker. Folders (and
 *  mixed file+folder selections) are handled by dragging them onto the page —
 *  the `webkitdirectory` picker can only select one folder and can't mix in
 *  loose files, so a dedicated folder button would only be more confusing. */
export function UploadMenu({ onFiles }: UploadMenuProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    if (files.length > 0) onFiles(files)
    e.target.value = ''
  }

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        aria-hidden="true"
        onChange={handleChange}
      />
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Upload className="size-4" aria-hidden="true" />
        Upload
      </button>
    </>
  )
}
