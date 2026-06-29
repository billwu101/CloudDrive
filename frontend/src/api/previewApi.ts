import type { PreviewInfoResponse } from './types'
import { api } from './client'

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
