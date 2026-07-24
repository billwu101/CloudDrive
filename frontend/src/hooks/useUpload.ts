import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import type { QuotaResponse } from '@/api/types'
import { driveApi } from '@/api/driveApi'
import { uploadApi } from '@/api/uploadApi'
import { authKeys } from '@/hooks/useAuth'
import { driveKeys } from '@/hooks/useDrive'
import {
  precheckBatch,
  runWithConcurrency,
  uploadErrorMessage,
  UPLOAD_CONCURRENCY,
} from '@/lib/uploadLimits'
import type { UploadTask } from '@/stores/uploadStore'
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

/**
 * Fail everything that provably cannot succeed before a single request is
 * sent, and mark the survivors as waiting for a slot. A doomed 2 GB file used
 * to hold a connection open until it failed, dragging the rest of the batch
 * down with it; now it never leaves the browser.
 */
function admitTasks(
  tasks: UploadTask[],
  availableBytes: number | undefined,
  markFailed: (id: string, error: string) => void,
  markQueued: (id: string) => void,
): UploadTask[] {
  const verdicts = precheckBatch(
    tasks.map((t) => t.file.size),
    availableBytes,
  )
  const admitted: UploadTask[] = []
  tasks.forEach((task, index) => {
    const rejection = verdicts[index]
    if (rejection) {
      markFailed(task.id, rejection.message)
      return
    }
    markQueued(task.id)
    admitted.push(task)
  })
  return admitted
}

export function useUploadFiles(parentId?: string) {
  const qc = useQueryClient()
  const { addTasks, markQueued, markUploading, updateProgress, markCompleted, markFailed } =
    useUploadStore()

  const upload = useCallback(
    async (files: File[]) => {
      const tasks = addTasks(files, parentId)
      const available = qc.getQueryData<QuotaResponse>(authKeys.quota())?.available_bytes
      const admitted = admitTasks(tasks, available, markFailed, markQueued)

      await runWithConcurrency(admitted, UPLOAD_CONCURRENCY, async (task) => {
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
          markFailed(task.id, uploadErrorMessage(err))
        }
      })

      // Refresh the quota so the next batch pre-checks against real numbers.
      qc.invalidateQueries({ queryKey: authKeys.quota() })
    },
    [
      parentId,
      addTasks,
      markQueued,
      markUploading,
      updateProgress,
      markCompleted,
      markFailed,
      qc,
    ],
  )

  return { upload }
}

/** Upload one or more folders, preserving their directory structure. Each file
 *  carries a relative path (e.g. "MyFolder/sub/a.txt"); the folder tree is
 *  recreated under `parentId` and each file uploaded into its folder. */
export function useUploadFolders(parentId?: string) {
  const qc = useQueryClient()
  const { addTasks, markQueued, markUploading, updateProgress, markCompleted, markFailed } =
    useUploadStore()

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
      const available = qc.getQueryData<QuotaResponse>(authKeys.quota())?.available_bytes
      const admitted = admitTasks(tasks, available, markFailed, markQueued)

      await runWithConcurrency(admitted, UPLOAD_CONCURRENCY, async (task) => {
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
          markFailed(task.id, uploadErrorMessage(err))
        }
      })

      qc.invalidateQueries({ queryKey: driveKeys.items(parentId) })
      qc.invalidateQueries({ queryKey: authKeys.quota() })
    },
    [
      parentId,
      addTasks,
      markQueued,
      markUploading,
      updateProgress,
      markCompleted,
      markFailed,
      qc,
    ],
  )

  return { uploadFolders }
}
