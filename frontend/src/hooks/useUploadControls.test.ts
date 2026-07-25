import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { rememberUpload, listPersistedUploads } from '@/lib/uploadPersistence'
import { useUploadStore } from '@/stores/uploadStore'

import { useUploadControls } from './useUpload'

const cancelSession = vi.fn()
const runChunkedUploadTask = vi.fn()

vi.mock('@/api/uploadApi', () => ({
  uploadApi: { cancelSession: (...a: unknown[]) => cancelSession(...a) },
}))
vi.mock('@/lib/chunkedUpload', async () => {
  const actual = await vi.importActual<typeof import('@/lib/chunkedUpload')>('@/lib/chunkedUpload')
  return { ...actual, runChunkedUploadTask: (...a: unknown[]) => runChunkedUploadTask(...a) }
})

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client: qc }, children)
}

function addChunkedTask(sessionId?: string) {
  const file = new File([new Uint8Array(16)], 'movie.bin')
  const [task] = useUploadStore.getState().addTasks([file], 'parent-1')
  if (sessionId) useUploadStore.getState().setSessionInfo(task.id, { sessionId, totalChunks: 2 })
  return task.id
}

beforeEach(() => {
  localStorage.clear()
  useUploadStore.setState({ tasks: [] })
})
afterEach(() => {
  cancelSession.mockReset()
  runChunkedUploadTask.mockReset()
})

describe('useUploadControls', () => {
  it('pause sets the task to paused (loop stops between chunks)', () => {
    const id = addChunkedTask('s1')
    const { result } = renderHook(() => useUploadControls(), { wrapper })

    act(() => result.current.pause(id))

    expect(useUploadStore.getState().tasks.find((t) => t.id === id)?.status).toBe('paused')
  })

  it('continue re-runs the chunked flow for the task', async () => {
    const id = addChunkedTask('s1')
    useUploadStore.getState().markPaused(id)
    runChunkedUploadTask.mockResolvedValue(true)
    const { result } = renderHook(() => useUploadControls(), { wrapper })

    await act(async () => {
      await result.current.continueUpload(id)
    })

    expect(runChunkedUploadTask).toHaveBeenCalledWith(id)
  })

  it('cancel deletes the server session and forgets it locally', async () => {
    const id = addChunkedTask('s1')
    rememberUpload({ sessionId: 's1', fileName: 'movie.bin', size: 16, parentId: 'parent-1' })
    cancelSession.mockResolvedValue({})
    const { result } = renderHook(() => useUploadControls(), { wrapper })

    await act(async () => {
      await result.current.cancel(id)
    })

    expect(useUploadStore.getState().tasks.find((t) => t.id === id)?.status).toBe('canceled')
    expect(cancelSession).toHaveBeenCalledWith('s1')
    expect(listPersistedUploads()).toEqual([])
  })

  it('cancel still succeeds locally when the server delete fails', async () => {
    const id = addChunkedTask('s1')
    cancelSession.mockRejectedValue(new Error('offline'))
    const { result } = renderHook(() => useUploadControls(), { wrapper })

    await act(async () => {
      await result.current.cancel(id)
    })

    expect(useUploadStore.getState().tasks.find((t) => t.id === id)?.status).toBe('canceled')
  })

  it('resumeWithFile rejects a file whose size does not match', async () => {
    const id = addChunkedTask('s1')
    // Task size is 16; hand it a different-sized file.
    const wrong = new File([new Uint8Array(8)], 'movie.bin')
    const { result } = renderHook(() => useUploadControls(), { wrapper })

    await act(async () => {
      await result.current.resumeWithFile(id, wrong)
    })

    const task = useUploadStore.getState().tasks.find((t) => t.id === id)
    expect(task?.status).toBe('failed')
    expect(runChunkedUploadTask).not.toHaveBeenCalled()
  })

  it('resumeWithFile attaches a matching file and continues', async () => {
    const id = addChunkedTask('s1')
    const right = new File([new Uint8Array(16)], 'movie.bin')
    runChunkedUploadTask.mockResolvedValue(true)
    const { result } = renderHook(() => useUploadControls(), { wrapper })

    await act(async () => {
      await result.current.resumeWithFile(id, right)
    })

    expect(useUploadStore.getState().tasks.find((t) => t.id === id)?.file).toBe(right)
    expect(runChunkedUploadTask).toHaveBeenCalledWith(id)
  })
})
