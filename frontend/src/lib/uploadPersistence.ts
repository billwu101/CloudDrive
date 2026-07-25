import type { UploadTask } from '@/stores/uploadStore'

/**
 * Chunked uploads survive a browser reload because the session lives on the
 * server; only a pointer to it needs to persist here. The File itself cannot
 * be serialized, so a restored task starts in `needs_file` and the user
 * re-picks the same file to continue (proposal §27.2).
 */
const STORAGE_KEY = 'clouddrive.uploads.v1'

export interface PersistedUpload {
  sessionId: string
  fileName: string
  size: number
  parentId?: string
}

function _read(): PersistedUpload[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (e): e is PersistedUpload =>
        typeof e === 'object' &&
        e !== null &&
        typeof (e as PersistedUpload).sessionId === 'string' &&
        typeof (e as PersistedUpload).fileName === 'string',
    )
  } catch {
    return []
  }
}

function _write(entries: PersistedUpload[]): void {
  try {
    if (entries.length === 0) localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // Storage may be full or blocked (private mode); resume is a nicety, not
    // load-bearing, so a failure here must never break an upload.
  }
}

/** Record (or update) an in-flight session so it can be resumed after reload. */
export function rememberUpload(entry: PersistedUpload): void {
  const entries = _read().filter((e) => e.sessionId !== entry.sessionId)
  entries.push(entry)
  _write(entries)
}

/** Drop a session once it is completed, cancelled, or abandoned. */
export function forgetUpload(sessionId: string): void {
  _write(_read().filter((e) => e.sessionId !== sessionId))
}

export function listPersistedUploads(): PersistedUpload[] {
  return _read()
}

/** Turn persisted pointers into queue tasks awaiting their file (`needs_file`). */
export function restoredTasksFromStorage(): UploadTask[] {
  return listPersistedUploads().map((e) => ({
    id: crypto.randomUUID(),
    file: null,
    fileName: e.fileName,
    size: e.size,
    parentId: e.parentId,
    progress: 0,
    status: 'needs_file' as const,
    controller: new AbortController(),
    sessionId: e.sessionId,
  }))
}
