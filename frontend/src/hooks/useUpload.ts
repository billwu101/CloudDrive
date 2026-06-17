import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { isApiError } from '@/api/client'
import { driveApi } from '@/api/driveApi'
import { uploadApi } from '@/api/uploadApi'
import { driveKeys } from '@/hooks/useDrive'
import { useUploadStore } from '@/stores/uploadStore'

/** A file's path relative to the upload root — webkitRelativePath for the
 *  directory picker, or `relativePath` we attach during a folder drag-drop. */
export function relativePathOf(file: File): string {
  const tagged = file as unknown as { relativePath?: string }
  return tagged.relativePath || file.webkitRelativePath || file.name
}

/** Create the folder (or find it if it already exists) and return its id. */
async function ensureFolder(name: string, parentId?: string): Promise<string> {
  try {
    const created = await driveApi.createFolder(name, parentId)
    return created.data.id
  } catch (err) {
    // Folder already exists (re-upload / merge): find it by name in the parent.
    const page = await driveApi.listItems({ parent_id: parentId, page_size: 1000 })
    const existing = page.data.items.find((i) => i.item_type === 'FOLDER' && i.name === name)
    if (existing) return existing.id
    throw err
  }
}

export function useUploadFiles(parentId?: string) {
  const qc = useQueryClient()
  const { addTasks, markUploading, updateProgress, markCompleted, markFailed } = useUploadStore()

  const upload = useCallback(
    async (files: File[]) => {
      const tasks = addTasks(files, parentId)

      await Promise.allSettled(
        tasks.map(async (task) => {
          markUploading(task.id)
          try {
            await uploadApi.uploadSimple(task.file, {
              parentId,
              signal: task.controller.signal,
              onProgress: (pct) => updateProgress(task.id, pct),
            })
            markCompleted(task.id)
            qc.invalidateQueries({ queryKey: driveKeys.items(parentId) })
          } catch (err) {
            if (task.controller.signal.aborted) return
            const msg = isApiError(err) ? err.message : 'Upload failed'
            markFailed(task.id, msg)
          }
        }),
      )
    },
    [parentId, addTasks, markUploading, updateProgress, markCompleted, markFailed, qc],
  )

  return { upload }
}

/** Upload one or more folders, preserving their directory structure. Each file
 *  carries a relative path (e.g. "MyFolder/sub/a.txt"); the folder tree is
 *  recreated under `parentId` and each file uploaded into its folder. */
export function useUploadFolders(parentId?: string) {
  const qc = useQueryClient()
  const { addTasks, markUploading, updateProgress, markCompleted, markFailed } = useUploadStore()

  const uploadFolders = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return

      // 1. Collect every directory path that needs to exist.
      const dirPaths = new Set<string>()
      for (const file of files) {
        const parts = relativePathOf(file).split('/')
        parts.pop() // drop the filename
        let acc = ''
        for (const part of parts) {
          acc = acc ? `${acc}/${part}` : part
          dirPaths.add(acc)
        }
      }

      // 2. Create folders parents-first, mapping each path to its new id.
      const idByPath = new Map<string, string>()
      const ordered = [...dirPaths].sort(
        (a, b) => a.split('/').length - b.split('/').length,
      )
      for (const path of ordered) {
        const name = path.split('/').pop() as string
        const parentPath = path.split('/').slice(0, -1).join('/')
        const parent = parentPath ? idByPath.get(parentPath) : parentId
        idByPath.set(path, await ensureFolder(name, parent))
      }

      // 3. Upload each file into its folder.
      const tasks = addTasks(files, parentId)
      await Promise.allSettled(
        tasks.map(async (task) => {
          markUploading(task.id)
          const dir = relativePathOf(task.file).split('/').slice(0, -1).join('/')
          const target = dir ? idByPath.get(dir) : parentId
          try {
            await uploadApi.uploadSimple(task.file, {
              parentId: target,
              signal: task.controller.signal,
              onProgress: (pct) => updateProgress(task.id, pct),
            })
            markCompleted(task.id)
          } catch (err) {
            if (task.controller.signal.aborted) return
            markFailed(task.id, isApiError(err) ? err.message : 'Upload failed')
          }
        }),
      )
      qc.invalidateQueries({ queryKey: driveKeys.items(parentId) })
    },
    [parentId, addTasks, markUploading, updateProgress, markCompleted, markFailed, qc],
  )

  return { uploadFolders }
}
