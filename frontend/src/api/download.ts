import { api } from './client'

/** Create an object URL for the blob and trigger a browser download, then clean up. */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/**
 * Download a single file with auth. Goes through the axios instance (Bearer
 * token + refresh) and saves the blob — a plain `<a href>` can't send the
 * Authorization header and would 401.
 */
export async function downloadItem(itemId: string, filename: string): Promise<void> {
  const res = await api.get<Blob>(`/download/${itemId}`, { responseType: 'blob' })
  triggerBlobDownload(res.data, filename)
}
