import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { authKeys } from '@/hooks/useAuth'
import { MAX_CHUNKED_UPLOAD_SIZE_BYTES, UPLOAD_CONCURRENCY } from '@/lib/uploadLimits'
import { useUploadStore } from '@/stores/uploadStore'

import { relativePathOf, useUploadFiles, useUploadFolders } from './useUpload'

const MB = 1024 * 1024

/** A File that reports `size` without allocating that many bytes. */
function fileOfSize(name: string, size: number): File {
  const file = new File(['x'], name, { type: 'application/octet-stream' })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

const createFolder = vi.fn()
const listItems = vi.fn()
const uploadSimple = vi.fn()

vi.mock('@/api/driveApi', () => ({
  driveApi: {
    createFolder: (...args: unknown[]) => createFolder(...args),
    listItems: (...args: unknown[]) => listItems(...args),
  },
}))
vi.mock('@/api/uploadApi', () => ({
  uploadApi: { uploadSimple: (...args: unknown[]) => uploadSimple(...args) },
}))

function fileWithPath(path: string): File {
  const file = new File(['x'], path.split('/').pop() as string, { type: 'text/plain' })
  ;(file as unknown as { relativePath?: string }).relativePath = path
  return file
}

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client: qc }, children)
}

afterEach(() => {
  useUploadStore.setState({ tasks: [] })
  createFolder.mockReset()
  listItems.mockReset()
  uploadSimple.mockReset()
})

describe('relativePathOf', () => {
  it('prefers an attached relativePath, then webkitRelativePath, then name', () => {
    expect(relativePathOf(fileWithPath('A/b/c.txt'))).toBe('A/b/c.txt')
    expect(relativePathOf(new File(['x'], 'plain.txt'))).toBe('plain.txt')
  })
})

describe('useUploadFolders', () => {
  it('recreates the folder tree and uploads each file into its folder', async () => {
    createFolder.mockImplementation((name: string) =>
      Promise.resolve({ data: { id: `id-${name}` } }),
    )
    uploadSimple.mockResolvedValue({ data: {} })

    const files = [
      fileWithPath('Root/a.txt'),
      fileWithPath('Root/sub/b.txt'),
    ]
    const { result } = renderHook(() => useUploadFolders(undefined), { wrapper })
    await act(async () => {
      await result.current.uploadFolders(files)
    })

    // Folders created parents-first: Root (at drive root), then sub (under Root).
    expect(createFolder).toHaveBeenCalledWith('Root', undefined)
    expect(createFolder).toHaveBeenCalledWith('sub', 'id-Root')

    await waitFor(() => expect(uploadSimple).toHaveBeenCalledTimes(2))
    const targets = uploadSimple.mock.calls.map((c) => [
      relativePathOf(c[0] as File),
      (c[1] as { parentId?: string }).parentId,
    ])
    expect(targets).toContainEqual(['Root/a.txt', 'id-Root'])
    expect(targets).toContainEqual(['Root/sub/b.txt', 'id-sub'])
  })

  it('reuses an existing folder when create conflicts', async () => {
    createFolder.mockRejectedValue({ message: 'exists' })
    listItems.mockResolvedValue({
      data: { items: [{ id: 'existing-root', name: 'Root', item_type: 'FOLDER' }] },
    })
    uploadSimple.mockResolvedValue({ data: {} })

    const { result } = renderHook(() => useUploadFolders(undefined), { wrapper })
    await act(async () => {
      await result.current.uploadFolders([fileWithPath('Root/a.txt')])
    })

    await waitFor(() => expect(uploadSimple).toHaveBeenCalledTimes(1))
    expect((uploadSimple.mock.calls[0][1] as { parentId?: string }).parentId).toBe('existing-root')
  })
})

describe('useUploadFiles pre-check', () => {
  it('fails a file past the 5 GB ceiling without ever sending a request', async () => {
    uploadSimple.mockResolvedValue({ data: {} })
    // Over the chunked ceiling: not even a session can rescue it, so it is
    // rejected up front rather than started.
    const huge = fileOfSize('movie.mp4', MAX_CHUNKED_UPLOAD_SIZE_BYTES + 1)
    const small = fileOfSize('note.txt', 10)

    const { result } = renderHook(() => useUploadFiles(undefined), { wrapper })
    await act(async () => {
      await result.current.upload([huge, small])
    })

    // Only the small file is sent; the doomed one never leaves the browser.
    expect(uploadSimple).toHaveBeenCalledTimes(1)
    expect((uploadSimple.mock.calls[0][0] as File).name).toBe('note.txt')

    const tasks = useUploadStore.getState().tasks
    const failed = tasks.find((t) => t.fileName === 'movie.mp4')
    expect(failed?.status).toBe('failed')
    expect(failed?.error).toContain('too large')
  })

  it('fails files that do not fit the remaining quota, cumulatively', async () => {
    uploadSimple.mockResolvedValue({ data: {} })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    // 25 MB left, three 10 MB files: the third cannot fit.
    qc.setQueryData(authKeys.quota(), {
      quota_bytes: 100 * MB,
      used_bytes: 75 * MB,
      available_bytes: 25 * MB,
      used_percent: 75,
    })
    const files = [
      fileOfSize('a.bin', 10 * MB),
      fileOfSize('b.bin', 10 * MB),
      fileOfSize('c.bin', 10 * MB),
    ]

    const { result } = renderHook(() => useUploadFiles(undefined), {
      wrapper: ({ children }: { children: ReactNode }) =>
        createElement(QueryClientProvider, { client: qc }, children),
    })
    await act(async () => {
      await result.current.upload(files)
    })

    expect(uploadSimple).toHaveBeenCalledTimes(2)
    const third = useUploadStore.getState().tasks.find((t) => t.file.name === 'c.bin')
    expect(third?.status).toBe('failed')
    expect(third?.error).toContain('storage space')
  })
})

describe('useUploadFiles concurrency', () => {
  it('uploads at most 3 at a time and leaves the rest queued', async () => {
    let inFlight = 0
    let peak = 0
    const release: Array<() => void> = []
    uploadSimple.mockImplementation(
      () =>
        new Promise((resolve) => {
          inFlight += 1
          peak = Math.max(peak, inFlight)
          release.push(() => {
            inFlight -= 1
            resolve({ data: {} })
          })
        }),
    )

    const files = Array.from({ length: 7 }, (_, i) => fileOfSize(`f${i}.txt`, 10))
    const { result } = renderHook(() => useUploadFiles(undefined), { wrapper })

    let done: Promise<void>
    await act(async () => {
      done = result.current.upload(files)
      await Promise.resolve()
    })

    // Exactly UPLOAD_CONCURRENCY requests are open; the rest wait their turn.
    await waitFor(() => expect(uploadSimple).toHaveBeenCalledTimes(UPLOAD_CONCURRENCY))
    const statuses = useUploadStore.getState().tasks.map((t) => t.status)
    expect(statuses.filter((s) => s === 'uploading')).toHaveLength(UPLOAD_CONCURRENCY)
    expect(statuses.filter((s) => s === 'queued')).toHaveLength(7 - UPLOAD_CONCURRENCY)

    // Draining the queue lets the waiting files through, still 3 at a time.
    await act(async () => {
      while (release.length > 0) {
        release.shift()?.()
        await Promise.resolve()
      }
      await done
    })

    expect(uploadSimple).toHaveBeenCalledTimes(7)
    expect(peak).toBe(UPLOAD_CONCURRENCY)
  })
})

describe('useUploadFiles error classification', () => {
  it.each([
    ['QUOTA_EXCEEDED', 413, 'storage space'],
    ['NETWORK_ERROR', 0, 'Connection lost'],
    ['FILE_TOO_LARGE', 413, 'too large'],
  ])('reports %s as a specific message', async (code, status, expected) => {
    uploadSimple.mockRejectedValue({ code, status, message: 'raw server text' })

    const { result } = renderHook(() => useUploadFiles(undefined), { wrapper })
    await act(async () => {
      await result.current.upload([fileOfSize('f.txt', 10)])
    })

    const task = useUploadStore.getState().tasks.find((t) => t.file.name === 'f.txt')
    expect(task?.status).toBe('failed')
    expect(task?.error).toContain(expected)
  })
})
