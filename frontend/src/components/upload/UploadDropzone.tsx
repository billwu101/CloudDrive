import { Upload } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'

interface UploadDropzoneProps {
  onFiles: (files: File[]) => void
  children: React.ReactNode
}

export function UploadDropzone({ onFiles, children }: UploadDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const enterCount = useRef(0)

  const onDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    enterCount.current++
    setDragging(true)
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    enterCount.current--
    if (enterCount.current === 0) setDragging(false)
  }, [])

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      enterCount.current = 0
      setDragging(false)
      const files = Array.from(e.dataTransfer.files).filter((f) => f.size > 0)
      if (files.length > 0) onFiles(files)
    },
    [onFiles],
  )

  return (
    <div
      className="relative flex-1"
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {children}

      {dragging && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-primary bg-primary/10 backdrop-blur-sm">
          <Upload className="size-10 text-primary" aria-hidden="true" />
          <p className="text-sm font-medium text-primary">Drop files to upload</p>
        </div>
      )}
    </div>
  )
}
