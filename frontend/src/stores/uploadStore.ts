import { create } from 'zustand'

export type UploadStatus = 'pending' | 'uploading' | 'completed' | 'failed' | 'canceled'

export interface UploadTask {
  id: string
  file: File
  parentId?: string
  progress: number
  status: UploadStatus
  error?: string
  controller: AbortController
}

interface UploadState {
  tasks: UploadTask[]
  addTasks: (files: File[], parentId?: string) => UploadTask[]
  updateProgress: (id: string, progress: number) => void
  markUploading: (id: string) => void
  markCompleted: (id: string) => void
  markFailed: (id: string, error: string) => void
  cancelTask: (id: string) => void
  removeTask: (id: string) => void
  clearCompleted: () => void
}

export const useUploadStore = create<UploadState>()((set, get) => ({
  tasks: [],

  addTasks: (files, parentId) => {
    const newTasks: UploadTask[] = files.map((file) => ({
      id: crypto.randomUUID(),
      file,
      parentId,
      progress: 0,
      status: 'pending',
      controller: new AbortController(),
    }))
    set((s) => ({ tasks: [...s.tasks, ...newTasks] }))
    return newTasks
  },

  updateProgress: (id, progress) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, progress } : t)),
    })),

  markUploading: (id) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, status: 'uploading' } : t)),
    })),

  markCompleted: (id) =>
    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.id === id ? { ...t, status: 'completed', progress: 100 } : t,
      ),
    })),

  markFailed: (id, error) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, status: 'failed', error } : t)),
    })),

  cancelTask: (id) => {
    const task = get().tasks.find((t) => t.id === id)
    task?.controller.abort()
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, status: 'canceled' } : t)),
    }))
  },

  removeTask: (id) =>
    set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),

  clearCompleted: () =>
    set((s) => ({
      tasks: s.tasks.filter((t) => t.status !== 'completed' && t.status !== 'canceled'),
    })),
}))
