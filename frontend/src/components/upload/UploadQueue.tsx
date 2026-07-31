import { useEffect } from 'react'

import { useUploadControls } from '@/hooks/useUpload'
import { restoredTasksFromStorage } from '@/lib/uploadPersistence'
import type { UploadTask } from '@/stores/uploadStore'
import { useUploadStore } from '@/stores/uploadStore'

import { UploadTaskItem } from './UploadTaskItem'

interface UploadQueueProps {
  onRetry: (task: UploadTask) => void
}

export function UploadQueue({ onRetry }: UploadQueueProps) {
  const tasks = useUploadStore((s) => s.tasks)
  const removeTask = useUploadStore((s) => s.removeTask)
  const clearCompleted = useUploadStore((s) => s.clearCompleted)
  const addRestoredTasks = useUploadStore((s) => s.addRestoredTasks)
  const { pause, continueUpload, cancel, resumeWithFile } = useUploadControls()

  // Surface sessions left unfinished on a previous visit so the user can
  // reselect the file and resume (the File itself can't be persisted).
  useEffect(() => {
    const restored = restoredTasksFromStorage()
    if (restored.length > 0) addRestoredTasks(restored)
  }, [addRestoredTasks])

  if (tasks.length === 0) return null

  const hasCompleted = tasks.some((t) => t.status === 'completed' || t.status === 'canceled')

  return (
    <div className="fixed bottom-4 right-4 z-40 w-80 rounded-lg border bg-popover shadow-xl">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <span className="text-sm font-medium">Uploads ({tasks.length})</span>
        {hasCompleted && (
          <button
            onClick={clearCompleted}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Clear done
          </button>
        )}
      </div>
      <ul className="max-h-64 overflow-y-auto space-y-1 p-2" aria-label="Upload queue">
        {tasks.map((task) => (
          <UploadTaskItem
            key={task.id}
            task={task}
            onCancel={cancel}
            onRetry={(t) => {
              // Retrying opens a *new* task, so the old failed row is no longer
              // this file's current state. Leaving it would mean a successful
              // retry ends with only the failure on screen — the new task
              // having quietly settled — which reads as "the retry failed"
              // (proposal §27.8).
              onRetry(t)
              removeTask(t.id)
            }}
            onRemove={removeTask}
            onPause={pause}
            onContinue={continueUpload}
            onResumeFile={resumeWithFile}
          />
        ))}
      </ul>
    </div>
  )
}
