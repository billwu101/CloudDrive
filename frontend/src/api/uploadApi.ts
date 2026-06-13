import type { DriveItemResponse } from './types'
import { api } from './client'

export interface UploadOptions {
  parentId?: string
  onProgress?: (percent: number) => void
  signal?: AbortSignal
}

export const uploadApi = {
  uploadSimple: (file: File, { parentId, onProgress, signal }: UploadOptions = {}) => {
    const form = new FormData()
    form.append('file', file)
    const params = parentId ? { parent_id: parentId } : undefined
    return api.post<DriveItemResponse>('/upload/simple', form, {
      params,
      signal,
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
  },
}
