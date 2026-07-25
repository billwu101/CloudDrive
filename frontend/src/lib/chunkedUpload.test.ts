import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useUploadStore } from '@/stores/uploadStore'

import { runChunkedUpload, runChunkedUploadTask } from './chunkedUpload'

const createSession = vi.fn()
const getSession = vi.fn()
const putChunk = vi.fn()
const completeSession = vi.fn()
const cancelSession = vi.fn()

vi.mock('@/api/uploadApi', () => ({
  uploadApi: {
    createSession: (...a: unknown[]) => createSession(...a),
    getSession: (...a: unknown[]) => getSession(...a),
    putChunk: (...a: unknown[]) => putChunk(...a),
    completeSession: (...a: unknown[]) => completeSession(...a),
    cancelSession: (...a: unknown[]) => cancelSession(...a),
  },
}))

vi.mock('@/api/client', () => ({
  isApiError: (e: unknown) =>
    typeof e === 'object' && e !== null && 'code' in e && 'status' in e,
}))

const CHUNK = 8

/** A File that yields real bytes for slice() but a controllable size. */
function makeFile(name: string, bytes: Uint8Array): File {
  return new File([bytes], name, { type: 'application/octet-stream' })
}

function addTask(file: File, sessionId?: string): string {
  const [task] = useUploadStore.getState().addTasks([file], undefined)
  if (sessionId) {
    useUploadStore.getState().setSessionInfo(task.id, { sessionId, totalChunks: 0 })
  }
  return task.id
}

beforeEach(() => {
  localStorage.removeItem('clouddrive.uploads.v1')
  useUploadStore.setState({ tasks: [] })
})

afterEach(() => {
  createSession.mockReset()
  getSession.mockReset()
  putChunk.mockReset()
  completeSession.mockReset()
  cancelSession.mockReset()
})

describe('runChunkedUpload', () => {
  it('creates a session, sends every chunk in order, then completes', async () => {
    const content = new Uint8Array(20).map((_, i) => i) // 3 chunks at size 8
    const id = addTask(makeFile('movie.bin', content))
    createSession.mockResolvedValue({
      data: { id: 'sess-1', chunk_size: CHUNK, total_chunks: 3, uploaded_chunks: [] },
    })
    putChunk.mockResolvedValue({})
    completeSession.mockResolvedValue({ data: { id: 'item-1', name: 'movie.bin' } })

    const { item } = await runChunkedUpload(id)

    expect(item.id).toBe('item-1')
    // Sent 0,1,2 in order.
    const indexes = putChunk.mock.calls.map((c) => c[1])
    expect(indexes).toEqual([0, 1, 2])
    expect(completeSession).toHaveBeenCalledWith('sess-1', expect.anything())

    const task = useUploadStore.getState().tasks.find((t) => t.id === id)
    expect(task?.status).toBe('completed')
    expect(task?.progress).toBe(100)
  })

  it('on resume sends only the missing chunks', async () => {
    const content = new Uint8Array(24) // 3 chunks
    const id = addTask(makeFile('resume.bin', content), 'sess-2')
    getSession.mockResolvedValue({
      data: { id: 'sess-2', chunk_size: CHUNK, total_chunks: 3, uploaded_chunks: [0, 2] },
    })
    putChunk.mockResolvedValue({})
    completeSession.mockResolvedValue({ data: { id: 'item-2', name: 'resume.bin' } })

    await runChunkedUpload(id)

    // Only the gap (index 1) is re-sent.
    expect(putChunk).toHaveBeenCalledTimes(1)
    expect(putChunk.mock.calls[0][1]).toBe(1)
    expect(createSession).not.toHaveBeenCalled()
  })

  it('persists the session while in flight and forgets it on completion', async () => {
    const content = new Uint8Array(8)
    const id = addTask(makeFile('p.bin', content))
    createSession.mockResolvedValue({
      data: { id: 'sess-3', chunk_size: CHUNK, total_chunks: 1, uploaded_chunks: [] },
    })
    putChunk.mockImplementation(() => {
      // Mid-flight the session must be persisted for reload-resume.
      expect(localStorage.getItem('clouddrive.uploads.v1')).toContain('sess-3')
      return Promise.resolve({})
    })
    completeSession.mockResolvedValue({ data: { id: 'item-3', name: 'p.bin' } })

    await runChunkedUpload(id)

    // Cleared once the upload is durable on the server.
    expect(localStorage.getItem('clouddrive.uploads.v1')).toBeNull()
  })

  it('retries a failing chunk before giving up', async () => {
    const content = new Uint8Array(8)
    const id = addTask(makeFile('r.bin', content))
    createSession.mockResolvedValue({
      data: { id: 'sess-4', chunk_size: CHUNK, total_chunks: 1, uploaded_chunks: [] },
    })
    putChunk
      .mockRejectedValueOnce({ code: 'NETWORK_ERROR', status: 0 })
      .mockResolvedValueOnce({})
    completeSession.mockResolvedValue({ data: { id: 'item-4', name: 'r.bin' } })

    await runChunkedUpload(id)

    expect(putChunk).toHaveBeenCalledTimes(2) // failed once, then succeeded
    expect(completeSession).toHaveBeenCalled()
  })
})

describe('runChunkedUploadTask', () => {
  it('stops without failing when the task is paused', async () => {
    const content = new Uint8Array(24) // 3 chunks
    const id = addTask(makeFile('pause.bin', content))
    createSession.mockResolvedValue({
      data: { id: 'sess-5', chunk_size: CHUNK, total_chunks: 3, uploaded_chunks: [] },
    })
    putChunk.mockImplementation((_s, index) => {
      // Pause after the first chunk lands.
      if (index === 0) useUploadStore.getState().markPaused(id)
      return Promise.resolve({})
    })

    const ok = await runChunkedUploadTask(id)

    expect(ok).toBe(false)
    expect(completeSession).not.toHaveBeenCalled()
    // Session survives for resume; still persisted.
    expect(localStorage.getItem('clouddrive.uploads.v1')).toContain('sess-5')
    const task = useUploadStore.getState().tasks.find((t) => t.id === id)
    expect(task?.status).toBe('paused')
  })

  it('marks the task failed with the classified code on a real error', async () => {
    const content = new Uint8Array(8)
    const id = addTask(makeFile('f.bin', content))
    createSession.mockRejectedValue({ code: 'QUOTA_EXCEEDED', status: 413, message: 'x' })

    const ok = await runChunkedUploadTask(id)

    expect(ok).toBe(false)
    const task = useUploadStore.getState().tasks.find((t) => t.id === id)
    expect(task?.status).toBe('failed')
    expect(task?.errorCode).toBe('QUOTA_EXCEEDED')
    expect(task?.error).toContain('storage space')
  })
})
