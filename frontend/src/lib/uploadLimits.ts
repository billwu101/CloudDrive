import { isApiError } from '@/api/client'

/**
 * Largest file the simple-upload path can carry, matching the backend's
 * `max_upload_size_bytes` setting (100 MB).
 *
 * The whole body has to land in a single request, so bigger files are lost
 * either at nginx's 110 MB body cap or to the memory and connection cost of a
 * multi-GB POST. Rejecting them here keeps a doomed upload from occupying one
 * of the few connections the rest of the batch needs. Chunked upload
 * (proposal §27) will turn this cap into the threshold that switches a file
 * over to the session flow instead of failing it.
 */
export const MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024

/**
 * How many files upload at once. Browsers allow only ~6 connections per
 * origin, so firing a whole drop in parallel left every request crawling and
 * timing out together; the rest of the batch waits its turn instead.
 */
export const UPLOAD_CONCURRENCY = 3

export type UploadRejectionCode = 'FILE_TOO_LARGE' | 'QUOTA_EXCEEDED'

export interface UploadRejection {
  code: UploadRejectionCode
  message: string
}

const TOO_LARGE_MESSAGE = `File is too large (max ${formatBytes(MAX_UPLOAD_SIZE_BYTES)})`
const QUOTA_MESSAGE = 'Not enough storage space left'

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value >= 10 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`
}

/**
 * Decide, before a single request goes out, which files in a batch cannot
 * succeed. Returns one entry per input size — `null` means "may be uploaded".
 *
 * Quota is spent cumulatively across the batch, so files that each fit on
 * their own but not together still fail up front. An `availableBytes` of
 * `undefined` means the quota has not been fetched yet; only the per-file size
 * limit applies in that case, and the server stays the final authority.
 */
export function precheckBatch(
  sizes: number[],
  availableBytes?: number,
): (UploadRejection | null)[] {
  let budget = availableBytes
  return sizes.map((size) => {
    if (size > MAX_UPLOAD_SIZE_BYTES) {
      return { code: 'FILE_TOO_LARGE', message: TOO_LARGE_MESSAGE }
    }
    if (budget !== undefined) {
      if (size > budget) return { code: 'QUOTA_EXCEEDED', message: QUOTA_MESSAGE }
      budget -= size
    }
    return null
  })
}

/**
 * Turn an upload failure into a message that says what actually went wrong,
 * rather than reporting every failure as a network error.
 */
export function uploadErrorMessage(err: unknown): string {
  if (!isApiError(err)) return 'Upload failed'
  switch (err.code) {
    case 'FILE_TOO_LARGE':
      return TOO_LARGE_MESSAGE
    case 'QUOTA_EXCEEDED':
      // The API answers 413 for quota too, so the code has to win over status.
      return QUOTA_MESSAGE
    case 'NETWORK_ERROR':
      return 'Connection lost — check your network and retry'
    default:
      // A body the proxy rejects never reaches the app, so it carries no code.
      if (err.status === 413) return TOO_LARGE_MESSAGE
      return err.message || 'Upload failed'
  }
}

/**
 * Run `worker` over every item with at most `limit` in flight at a time.
 * Failures are contained per item, keeping the all-settled semantics the
 * caller had before the queue replaced `Promise.allSettled`.
 */
export async function runWithConcurrency<T>(
  items: T[],
  limit: number,
  worker: (item: T) => Promise<void>,
): Promise<void> {
  let cursor = 0
  const runners = Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, async () => {
    while (cursor < items.length) {
      const item = items[cursor] as T
      cursor += 1
      try {
        await worker(item)
      } catch {
        // Per-item outcomes are recorded by the worker itself.
      }
    }
  })
  await Promise.all(runners)
}
