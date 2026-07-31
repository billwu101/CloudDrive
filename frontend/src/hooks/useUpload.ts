import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import type { QuotaResponse } from '@/api/types'
import { isApiError } from '@/api/client'
import { driveApi } from '@/api/driveApi'
import { uploadApi } from '@/api/uploadApi'
import { authKeys } from '@/hooks/useAuth'
import { driveKeys } from '@/hooks/useDrive'
import { CHUNKED_UPLOAD_THRESHOLD, runChunkedUploadTask } from '@/lib/chunkedUpload'
import { forgetUpload } from '@/lib/uploadPersistence'
import {
  MAX_CHUNKED_UPLOAD_SIZE_BYTES,
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
 * sent, and mark the survivors as waiting for a slot. A doomed >5 GB file used
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
    tasks.map((t) => t.size),
    availableBytes,
    MAX_CHUNKED_UPLOAD_SIZE_BYTES,
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

/**
 * Upload one file. Files at or above the threshold take the chunked resumable
 * path; everything else goes through the single-request simple path. Returns
 * true only when the file was fully stored.
 */
async function uploadOne(task: UploadTask, targetParentId: string | undefined): Promise<boolean> {
  const store = useUploadStore.getState()
  if (task.file === null) return false

  if (task.file.size >= CHUNKED_UPLOAD_THRESHOLD) {
    return runChunkedUploadTask(task.id)
  }

  store.markUploading(task.id)
  try {
    await uploadApi.uploadSimple(task.file, {
      parentId: targetParentId,
      signal: task.controller.signal,
      onProgress: (pct) => useUploadStore.getState().updateProgress(task.id, pct),
    })
    useUploadStore.getState().markCompleted(task.id)
    return true
  } catch (err) {
    if (task.controller.signal.aborted) return false
    useUploadStore
      .getState()
      .markFailed(task.id, uploadErrorMessage(err), isApiError(err) ? err.code : undefined)
    return false
  }
}

export function useUploadFiles(parentId?: string) {
  const qc = useQueryClient()
  const { addTasks, markQueued, markFailed, settleBatch } = useUploadStore()

  const upload = useCallback(
    async (files: File[]) => {
      const tasks = addTasks(files, parentId)
      const available = qc.getQueryData<QuotaResponse>(authKeys.quota())?.available_bytes
      const admitted = admitTasks(tasks, available, markFailed, markQueued)

      await runWithConcurrency(admitted, UPLOAD_CONCURRENCY, async (task) => {
        const ok = await uploadOne(task, parentId)
        if (ok) qc.invalidateQueries({ queryKey: driveKeys.items(parentId) })
      })

      // Refresh the quota so the next batch pre-checks against real numbers.
      qc.invalidateQueries({ queryKey: authKeys.quota() })
      // The round is over: let its successes go, keep everything else (§27.8).
      settleBatch(tasks.map((t) => t.id))
    },
    [parentId, addTasks, markQueued, markFailed, settleBatch, qc],
  )

  return { upload }
}

/** Upload one or more folders, preserving their directory structure. Each file
 *  carries a relative path (e.g. "MyFolder/sub/a.txt"); the folder tree is
 *  recreated under `parentId` and each file uploaded into its folder. */
export function useUploadFolders(parentId?: string) {
  const qc = useQueryClient()
  const { addTasks, markQueued, markFailed, settleBatch } = useUploadStore()

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
      const ordered = [...dirPaths].sort((a, b) => a.split('/').length - b.split('/').length)
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
        const dir = relativePathOf(task.file ?? new File([], task.fileName))
          .split('/')
          .slice(0, -1)
          .join('/')
        const target = dir ? idByPath.get(dir) : parentId
        await uploadOne(task, target)
      })

      qc.invalidateQueries({ queryKey: driveKeys.items(parentId) })
      qc.invalidateQueries({ queryKey: authKeys.quota() })
      settleBatch(tasks.map((t) => t.id))
    },
    [parentId, addTasks, markQueued, markFailed, settleBatch, qc],
  )

  return { uploadFolders }
}

/**
 * Pause / continue / cancel / resume controls for chunked uploads. Kept apart
 * from the batch hooks so the queue UI can drive individual tasks.
 */
export function useUploadControls() {
  const qc = useQueryClient()
  const { markPaused, cancelTask, attachFile } = useUploadStore()

  const pause = useCallback(
    (id: string) => {
      // The chunked loop checks status between chunks and stops; the session
      // stays alive on the server so it can resume later.
      markPaused(id)
    },
    [markPaused],
  )

  const continueUpload = useCallback(
    async (id: string) => {
      const task = useUploadStore.getState().tasks.find((t) => t.id === id)
      if (!task || task.file === null) return
      // A fresh controller: a prior cancel would have aborted the old one.
      task.controller = new AbortController()
      const ok = await runChunkedUploadTask(id)
      if (ok) {
        qc.invalidateQueries({ queryKey: driveKeys.items(task.parentId) })
        qc.invalidateQueries({ queryKey: authKeys.quota() })
      }
    },
    [qc],
  )

  const cancel = useCallback(
    async (id: string) => {
      const task = useUploadStore.getState().tasks.find((t) => t.id === id)
      cancelTask(id)
      if (task?.sessionId) {
        forgetUpload(task.sessionId)
        // Best-effort: reclaim the server's chunks. A failure here is harmless
        // — the cleanup job will collect an abandoned session anyway.
        try {
          await uploadApi.cancelSession(task.sessionId)
        } catch {
          /* ignore */
        }
      }
    },
    [cancelTask],
  )

  /** Re-attach a file to a session restored from a previous visit, then resume. */
  const resumeWithFile = useCallback(
    async (id: string, file: File) => {
      const task = useUploadStore.getState().tasks.find((t) => t.id === id)
      if (!task) return
      if (file.size !== task.size) {
        useUploadStore
          .getState()
          .markFailed(id, 'Selected file does not match the paused upload', 'FILE_MISMATCH')
        return
      }
      attachFile(id, file)
      await continueUpload(id)
    },
    [attachFile, continueUpload],
  )

  return { pause, continueUpload, cancel, resumeWithFile }
}
