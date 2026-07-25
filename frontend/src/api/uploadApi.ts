import type { DriveItemResponse, UploadSessionResponse } from './types'
import { api } from './client'

export interface UploadOptions {
  parentId?: string
  onProgress?: (percent: number) => void
  signal?: AbortSignal
}

export interface CreateSessionArgs {
  filename: string
  totalSize: number
  parentId?: string
  mimeType?: string | null
}

export const uploadApi = {
  uploadSimple: (file: File, { parentId, onProgress, signal }: UploadOptions = {}) => {
    const form = new FormData()
    form.append('file', file)
    const params = parentId ? { parent_id: parentId } : undefined
    // XHR adapter (not the client-default fetch): a FormData body survives the
    // 401→refresh→retry that the fetch adapter would break by consuming it once.
    return api.post<DriveItemResponse>('/upload/simple', form, {
      params,
      signal,
      adapter: 'xhr',
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
  },

  // ── Chunked resumable upload (proposal §27) ────────────────────────────────

  createSession: ({ filename, totalSize, parentId, mimeType }: CreateSessionArgs) =>
    api.post<UploadSessionResponse>('/upload/sessions', {
      filename,
      total_size: totalSize,
      parent_id: parentId ?? null,
      mime_type: mimeType ?? null,
    }),

  getSession: (sessionId: string, signal?: AbortSignal) =>
    api.get<UploadSessionResponse>(`/upload/sessions/${sessionId}`, { signal }),

  // The chunk is sent as the raw request body (not multipart), so a chunk
  // never lands in the server's memory whole.
  putChunk: (sessionId: string, index: number, chunk: Blob, signal?: AbortSignal) =>
    api.put<void>(`/upload/sessions/${sessionId}/chunks/${index}`, chunk, {
      signal,
      // XHR adapter so a Blob body survives a 401→refresh→retry (see uploadSimple).
      adapter: 'xhr',
      headers: { 'Content-Type': 'application/octet-stream' },
    }),

  completeSession: (sessionId: string, signal?: AbortSignal) =>
    api.post<DriveItemResponse>(`/upload/sessions/${sessionId}/complete`, undefined, { signal }),

  cancelSession: (sessionId: string) => api.delete<void>(`/upload/sessions/${sessionId}`),
}
