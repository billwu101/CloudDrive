import type { PreviewInfoResponse } from './types'
import { api } from './client'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const previewApi = {
  getInfo: (itemId: string, signal?: AbortSignal) =>
    api.get<PreviewInfoResponse>(`/preview/${itemId}`, { signal }),

  /**
   * Fetch preview content as a Blob. Goes through the axios instance so it
   * carries the Bearer token (and refresh) — unlike `<iframe>`/`<img>` src,
   * which can't send Authorization and would 401. `converted: true` hits the
   * preview endpoint that turns Office/CSV files into PDF.
   */
  getContentBlob: (itemId: string, opts?: { converted?: boolean }) =>
    api.get<Blob>(opts?.converted ? `/preview/${itemId}/content` : `/download/${itemId}`, {
      responseType: 'blob',
    }),
}

/** Direct content URL (no auth header) — used only for the download link on
 *  unsupported types, where the browser handles the navigation. */
export function getContentUrl(itemId: string): string {
  return `${BASE_URL}/download/${itemId}`
}
