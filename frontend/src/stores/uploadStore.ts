import { create } from 'zustand'

/** `queued` = accepted and waiting for a free upload slot (see
 *  UPLOAD_CONCURRENCY); `pending` = created but not yet handed to the queue;
 *  `paused` = a chunked upload the user stopped mid-way (session kept alive so
 *  it can resume); `needs_file` = a chunked upload restored from a previous
 *  visit whose File the browser can't recover — the user must re-pick it. */
export type UploadStatus =
  | 'pending'
  | 'queued'
  | 'uploading'
  | 'paused'
  | 'needs_file'
  | 'completed'
  | 'failed'
  | 'canceled'

export interface UploadTask {
  id: string
  file: File | null
  fileName: string
  size: number
  parentId?: string
  progress: number
  status: UploadStatus
  error?: string
  /** Server error code behind `error`, for classified messaging. */
  errorCode?: string
  controller: AbortController
  // ── Chunked upload (proposal §27); undefined for the simple path ──
  sessionId?: string
  totalChunks?: number
  /** Indexes already stored server-side; drives resume (send only the gaps). */
  uploadedChunks?: number[]
}

interface UploadState {
  tasks: UploadTask[]
  addTasks: (files: File[], parentId?: string) => UploadTask[]
  addRestoredTasks: (tasks: UploadTask[]) => void
  updateProgress: (id: string, progress: number) => void
  markQueued: (id: string) => void
  markUploading: (id: string) => void
  markPaused: (id: string) => void
  markCompleted: (id: string) => void
  markFailed: (id: string, error: string, errorCode?: string) => void
  setSessionInfo: (id: string, info: { sessionId: string; totalChunks: number }) => void
  setUploadedChunks: (id: string, indexes: number[]) => void
  attachFile: (id: string, file: File) => void
  cancelTask: (id: string) => void
  removeTask: (id: string) => void
  clearCompleted: () => void
}

function _newTask(file: File, parentId?: string): UploadTask {
  return {
    id: crypto.randomUUID(),
    file,
    fileName: file.name,
    size: file.size,
    parentId,
    progress: 0,
    status: 'pending',
    controller: new AbortController(),
  }
}

export const useUploadStore = create<UploadState>()((set, get) => ({
  tasks: [],

  addTasks: (files, parentId) => {
    const newTasks = files.map((file) => _newTask(file, parentId))
    set((s) => ({ tasks: [...s.tasks, ...newTasks] }))
    return newTasks
  },

  addRestoredTasks: (tasks) =>
    set((s) => {
      // Don't re-add a session that's already in the queue this session.
      const known = new Set(s.tasks.map((t) => t.sessionId).filter(Boolean))
      const fresh = tasks.filter((t) => !t.sessionId || !known.has(t.sessionId))
      return { tasks: [...s.tasks, ...fresh] }
    }),

  updateProgress: (id, progress) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, progress } : t)),
    })),

  markQueued: (id) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, status: 'queued' } : t)),
    })),

  markUploading: (id) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, status: 'uploading' } : t)),
    })),

  markPaused: (id) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, status: 'paused' } : t)),
    })),

  markCompleted: (id) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, status: 'completed', progress: 100 } : t)),
    })),

  markFailed: (id, error, errorCode) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, status: 'failed', error, errorCode } : t)),
    })),

  setSessionInfo: (id, info) =>
    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.id === id ? { ...t, sessionId: info.sessionId, totalChunks: info.totalChunks } : t,
      ),
    })),

  setUploadedChunks: (id, indexes) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, uploadedChunks: indexes } : t)),
    })),

  attachFile: (id, file) =>
    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.id === id ? { ...t, file, fileName: file.name, size: file.size } : t,
      ),
    })),

  cancelTask: (id) => {
    const task = get().tasks.find((t) => t.id === id)
    task?.controller.abort()
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, status: 'canceled' } : t)),
    }))
  },

  removeTask: (id) => set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),

  clearCompleted: () =>
    set((s) => ({
      tasks: s.tasks.filter((t) => t.status !== 'completed' && t.status !== 'canceled'),
    })),
}))
