import { isApiError } from '@/api/client'
import type { DriveItemResponse } from '@/api/types'
import { uploadApi } from '@/api/uploadApi'
import { useUploadStore } from '@/stores/uploadStore'

import { forgetUpload, rememberUpload } from './uploadPersistence'
import { uploadErrorMessage } from './uploadLimits'

/** Files at or above this use a chunked session; smaller ones use /upload/simple.
 *  Matches the backend `chunked_upload_threshold_bytes` so the two paths meet. */
export const CHUNKED_UPLOAD_THRESHOLD = 100 * 1024 * 1024

/** How many times a single chunk is retried before the whole upload fails
 *  (but keeps its session, so the user can resume). */
const CHUNK_RETRY_LIMIT = 3

class UploadAbortedError extends Error {}
class UploadPausedError extends Error {}

function _isAbort(err: unknown): boolean {
  return (
    (isApiError(err) && err.code === 'CANCELED') ||
    (err instanceof DOMException && err.name === 'AbortError')
  )
}

const _sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function _putChunkWithRetry(
  sessionId: string,
  index: number,
  chunk: Blob,
  signal: AbortSignal,
): Promise<void> {
  let attempt = 0
  for (;;) {
    try {
      await uploadApi.putChunk(sessionId, index, chunk, signal)
      return
    } catch (err) {
      if (_isAbort(err)) throw new UploadAbortedError()
      attempt += 1
      if (attempt > CHUNK_RETRY_LIMIT) throw err
      // Back off a little before retrying a flaky chunk.
      await _sleep(300 * attempt)
    }
  }
}

export interface ChunkedUploadResult {
  item: DriveItemResponse
}

/**
 * Drive one file through the chunked flow: create (or resume) a session, send
 * the missing chunks sequentially, then complete. Between chunks it checks the
 * task's live status so a pause or cancel takes effect without aborting the
 * chunk in flight.
 *
 * Resolves with the created item on success. Throws `UploadPausedError` when
 * paused (session kept), `UploadAbortedError` when cancelled, or a normal
 * error when it genuinely fails (session kept for a later resume).
 */
export async function runChunkedUpload(taskId: string): Promise<ChunkedUploadResult> {
  const store = useUploadStore.getState()
  const task = store.tasks.find((t) => t.id === taskId)
  if (!task || task.file === null) {
    throw new Error('Upload task has no file to send')
  }
  const { file, parentId, controller } = task
  const signal = controller.signal

  // 1. Establish the session — create a new one, or re-read an existing one to
  //    learn which chunks already made it (resume).
  let sessionId = task.sessionId
  let chunkSize: number
  let totalChunks: number
  const done = new Set<number>()

  if (sessionId) {
    const { data } = await uploadApi.getSession(sessionId, signal)
    chunkSize = data.chunk_size
    totalChunks = data.total_chunks
    data.uploaded_chunks.forEach((i) => done.add(i))
  } else {
    const { data } = await uploadApi.createSession({
      filename: file.name,
      totalSize: file.size,
      parentId,
      mimeType: file.type || null,
    })
    sessionId = data.id
    chunkSize = data.chunk_size
    totalChunks = data.total_chunks
    data.uploaded_chunks.forEach((i) => done.add(i))
    useUploadStore.getState().setSessionInfo(taskId, { sessionId, totalChunks })
  }

  rememberUpload({ sessionId, fileName: file.name, size: file.size, parentId })

  const st = useUploadStore.getState()
  st.markUploading(taskId)
  st.setUploadedChunks(taskId, [...done].sort((a, b) => a - b))
  const reportProgress = () => {
    // Reserve the last step for the merge on the server.
    const pct = totalChunks === 0 ? 99 : Math.floor((done.size / totalChunks) * 99)
    useUploadStore.getState().updateProgress(taskId, pct)
  }
  reportProgress()

  // 2. Send the gaps, in order (proposal §27.7: chunks are sequential).
  for (let index = 0; index < totalChunks; index += 1) {
    if (done.has(index)) continue

    const current = useUploadStore.getState().tasks.find((t) => t.id === taskId)
    if (!current || current.status === 'canceled') throw new UploadAbortedError()
    if (current.status === 'paused') throw new UploadPausedError()

    const start = index * chunkSize
    const chunk = file.slice(start, Math.min(start + chunkSize, file.size))
    await _putChunkWithRetry(sessionId, index, chunk, signal)

    done.add(index)
    const store2 = useUploadStore.getState()
    store2.setUploadedChunks(
      taskId,
      [...done].sort((a, b) => a - b),
    )
    reportProgress()
  }

  // 3. Merge into the final file.
  const { data: item } = await uploadApi.completeSession(sessionId, signal)
  forgetUpload(sessionId)
  useUploadStore.getState().markCompleted(taskId)
  return { item }
}

/**
 * Run a chunked upload and fold every outcome back into the store. Returns
 * true only when the file was fully stored, so the caller knows to refresh
 * the listing. Pause and cancel are expected outcomes, not failures.
 */
export async function runChunkedUploadTask(taskId: string): Promise<boolean> {
  try {
    await runChunkedUpload(taskId)
    return true
  } catch (err) {
    if (err instanceof UploadPausedError) return false
    if (err instanceof UploadAbortedError || _isAbort(err)) return false
    const code = isApiError(err) ? err.code : undefined
    useUploadStore.getState().markFailed(taskId, uploadErrorMessage(err), code)
    return false
  }
}

export { UploadAbortedError, UploadPausedError }
