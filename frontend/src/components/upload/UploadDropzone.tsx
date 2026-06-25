import { Upload } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

interface UploadDropzoneProps {
  onFiles: (files: File[]) => void
  /** Called when one or more folders are dropped — files carry `relativePath`. */
  onFolders?: (files: File[]) => void
  children: React.ReactNode
}

function readAllEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  // readEntries returns at most ~100 at a time; call until it returns none.
  return new Promise((resolve, reject) => {
    const all: FileSystemEntry[] = []
    const next = () =>
      reader.readEntries((batch) => {
        if (batch.length === 0) resolve(all)
        else {
          all.push(...batch)
          next()
        }
      }, reject)
    next()
  })
}

async function walkEntry(entry: FileSystemEntry, prefix: string, out: File[]): Promise<void> {
  if (entry.isFile) {
    const file = await new Promise<File>((res, rej) =>
      (entry as FileSystemFileEntry).file(res, rej),
    )
    ;(file as unknown as { relativePath?: string }).relativePath = prefix + entry.name
    out.push(file)
  } else if (entry.isDirectory) {
    const children = await readAllEntries((entry as FileSystemDirectoryEntry).createReader())
    for (const child of children) await walkEntry(child, `${prefix}${entry.name}/`, out)
  }
}

export function UploadDropzone({ onFiles, onFolders, children }: UploadDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const enterCount = useRef(0)

  const handleFiles = useCallback(
    (e: DragEvent) => {
      e.preventDefault()
      enterCount.current = 0
      setDragging(false)

      // If folders were dropped, walk them (preserving structure) via the
      // entries API; otherwise fall back to the flat file list.
      const items = Array.from(e.dataTransfer?.items ?? [])
      const entries = items
        .map((it) => it.webkitGetAsEntry?.())
        .filter((en): en is FileSystemEntry => en != null)
      if (onFolders && entries.some((en) => en.isDirectory)) {
        void (async () => {
          const collected: File[] = []
          for (const entry of entries) await walkEntry(entry, '', collected)
          const nonEmpty = collected.filter((f) => f.size > 0)
          if (nonEmpty.length > 0) onFolders(nonEmpty)
        })()
        return
      }

      const files = Array.from(e.dataTransfer?.files ?? []).filter((f) => f.size > 0)
      if (files.length > 0) onFiles(files)
    },
    [onFiles, onFolders],
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
          <p className="text-sm font-medium text-primary">Drop files or folders to upload</p>
        </div>
      )}
    </>
  )
}
