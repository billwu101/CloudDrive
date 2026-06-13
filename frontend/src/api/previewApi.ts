import type { PreviewInfoResponse } from './types'
import { api } from './client'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const previewApi = {
  getInfo: (itemId: string, signal?: AbortSignal) =>
    api.get<PreviewInfoResponse>(`/preview/${itemId}/info`, { signal }),
}

/** Returns the URL used to stream file content for preview or download. */
export function getContentUrl(itemId: string): string {
  return `${BASE_URL}/download/${itemId}`
}
