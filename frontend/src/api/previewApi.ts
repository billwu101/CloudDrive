import type { PreviewInfoResponse } from './types'
import { api } from './client'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const previewApi = {
  getInfo: (itemId: string, signal?: AbortSignal) =>
    api.get<PreviewInfoResponse>(`/preview/${itemId}`, { signal }),
}

/** Returns the URL used to stream file content for preview or download. */
export function getContentUrl(itemId: string): string {
  return `${BASE_URL}/download/${itemId}`
}

/**
 * Preview-content endpoint. Use this for `document` previews: the server
 * converts Office/CSV files to PDF here (the raw download would be the
 * original, unviewable file).
 */
export function getPreviewContentUrl(itemId: string): string {
  return `${BASE_URL}/preview/${itemId}/content`
}
