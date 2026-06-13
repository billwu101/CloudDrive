import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { isApiError } from '@/api/client'
import { uploadApi } from '@/api/uploadApi'
import { driveKeys } from '@/hooks/useDrive'
import { useUploadStore } from '@/stores/uploadStore'

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
