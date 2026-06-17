import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { relativePathOf, useUploadFolders } from './useUpload'

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
