import type { UploadTask } from '@/stores/uploadStore'
import { useUploadStore } from '@/stores/uploadStore'

import { UploadTaskItem } from './UploadTaskItem'

interface UploadQueueProps {
  onRetry: (task: UploadTask) => void
}

export function UploadQueue({ onRetry }: UploadQueueProps) {
  const tasks = useUploadStore((s) => s.tasks)
  const cancelTask = useUploadStore((s) => s.cancelTask)
  const removeTask = useUploadStore((s) => s.removeTask)
  const clearCompleted = useUploadStore((s) => s.clearCompleted)

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
            onCancel={cancelTask}
            onRetry={onRetry}
            onRemove={removeTask}
          />
        ))}
      </ul>
    </div>
  )
}
