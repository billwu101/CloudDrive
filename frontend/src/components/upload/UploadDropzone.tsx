import { Upload } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

interface UploadDropzoneProps {
  onFiles: (files: File[]) => void
  children: React.ReactNode
}

export function UploadDropzone({ onFiles, children }: UploadDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const enterCount = useRef(0)

  const handleFiles = useCallback(
    (e: DragEvent) => {
      e.preventDefault()
      enterCount.current = 0
      setDragging(false)
      const files = Array.from(e.dataTransfer?.files ?? []).filter((f) => f.size > 0)
      if (files.length > 0) onFiles(files)
    },
    [onFiles],
  )

  useEffect(() => {
    const onDragEnter = (e: DragEvent) => {
      if (!e.dataTransfer?.types.includes('Files')) return
      e.preventDefault()
      enterCount.current++
      setDragging(true)
    }
    const onDragLeave = (e: DragEvent) => {
      e.preventDefault()
      enterCount.current = Math.max(0, enterCount.current - 1)
      if (enterCount.current === 0) setDragging(false)
    }
    const onDragOver = (e: DragEvent) => {
      if (e.dataTransfer?.types.includes('Files')) e.preventDefault()
    }

    window.addEventListener('dragenter', onDragEnter)
    window.addEventListener('dragleave', onDragLeave)
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('drop', handleFiles)
    return () => {
      window.removeEventListener('dragenter', onDragEnter)
      window.removeEventListener('dragleave', onDragLeave)
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('drop', handleFiles)
    }
  }, [handleFiles])

  return (
    <>
      {children}
      {dragging && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-3 border-2 border-dashed border-primary bg-primary/10 backdrop-blur-sm">
          <Upload className="size-10 text-primary" aria-hidden="true" />
          <p className="text-sm font-medium text-primary">Drop files to upload</p>
        </div>
      )}
    </>
  )
}
