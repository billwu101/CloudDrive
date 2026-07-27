import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import type { DriveItemResponse } from '@/api/types'
import { useAuthStore } from '@/stores/authStore'

import { DRAG_MIME, useDragMove } from './useDragMove'

const BASE = 'http://localhost:8000/api/v1'

function item(id: string, name: string, type: 'FILE' | 'FOLDER'): DriveItemResponse {
  return {
    id,
    owner_id: 'u1',
    parent_id: null,
    item_type: type,
    name,
    mime_type: null,
    extension: null,
    size_bytes: 0,
    is_starred: false,
    is_deleted: false,
    deleted_at: null,
    created_by: 'u1',
    updated_by: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    is_shared_with_users: false,
    has_active_public_link: false,
  }
}

const FOLDER = item('folder-1', 'Target', 'FOLDER')
const FILE_A = item('file-a', 'a.txt', 'FILE')
const FILE_B = item('file-b', 'b.txt', 'FILE')
const ITEMS = [FOLDER, FILE_A, FILE_B]

/** A DragEvent stand-in carrying just the bits the hook reads. */
let lastDragImage: HTMLElement | null = null

function dragEvent(types: string[], payload?: string) {
  let prevented = false
  return {
    preventDefault: () => {
      prevented = true
    },
    stopPropagation: () => {},
    get defaultPrevented() {
      return prevented
    },
    dataTransfer: {
      types,
      effectAllowed: '',
      dropEffect: '',
      setData(_type: string, value: string) {
        payload = value
      },
      getData: () => payload ?? '',
      setDragImage(node: HTMLElement) {
        // Snapshot the node's text now: the hook removes it right afterwards.
        lastDragImage = node.cloneNode(true) as HTMLElement
      },
    },
  } as unknown as React.DragEvent & { defaultPrevented: boolean }
}

let moves: { id: string; parent: string | null }[] = []
let conflictOn: string | null = null

const server = setupServer(
  http.patch(`${BASE}/drive/items/:id/parent`, async ({ params, request }) => {
    const id = String(params['id'])
    const body = (await request.json()) as { parent_id: string | null }
    if (id === conflictOn) {
      return HttpResponse.json(
        { code: 'NAME_CONFLICT', message: "'b.txt' already exists in destination" },
        { status: 409 },
      )
    }
    moves.push({ id, parent: body.parent_id })
    return HttpResponse.json(item(id, 'moved', 'FILE'))
  }),
  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ code: 'UNAUTHORIZED' }, { status: 401 }),
  ),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterEach(() => {
  server.resetHandlers()
  moves = []
  conflictOn = null
})
afterAll(() => server.close())

function setup(selected: string[] = []) {
  useAuthStore.setState({ accessToken: 'test-token' })
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  return renderHook(() => useDragMove({ selectedIds: new Set(selected), items: ITEMS }), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  })
}

describe('useDragMove', () => {
  it('moves a single dragged item into the folder', async () => {
    const { result } = setup()
    act(() => result.current.onItemDragStart(FILE_A, dragEvent([])))
    act(() =>
      result.current.onItemDrop(FOLDER, dragEvent([DRAG_MIME], JSON.stringify(['file-a']))),
    )

    await waitFor(() => expect(moves).toEqual([{ id: 'file-a', parent: 'folder-1' }]))
  })

  it('moves the whole selection when the dragged item is part of it', async () => {
    const { result } = setup(['file-a', 'file-b'])
    const start = dragEvent([])
    act(() => result.current.onItemDragStart(FILE_A, start))

    // The payload the hook wrote is what a real drop would hand back.
    act(() =>
      result.current.onItemDrop(
        FOLDER,
        dragEvent([DRAG_MIME], JSON.stringify(['file-a', 'file-b'])),
      ),
    )

    await waitFor(() => expect(moves).toHaveLength(2))
    expect(moves.map((m) => m.id).sort()).toEqual(['file-a', 'file-b'])
  })

  it('moves only the dragged item when it is outside the selection', () => {
    const { result } = setup(['file-b'])
    act(() => result.current.onItemDragStart(FILE_A, dragEvent([])))

    // Dragging is a move gesture, not a selection one — the existing
    // selection must survive untouched.
    expect(result.current.draggingIds).toEqual(new Set(['file-a']))
  })

  it('refuses to drop on a file', () => {
    const { result } = setup()
    const over = dragEvent([DRAG_MIME])
    act(() => result.current.onItemDragOver(FILE_B, over))

    expect(over.defaultPrevented).toBe(false)
    expect(result.current.dropTargetId).toBeNull()
  })

  it('refuses to drop an item on itself', () => {
    const { result } = setup()
    act(() => result.current.onItemDragStart(FOLDER, dragEvent([])))
    const over = dragEvent([DRAG_MIME])
    act(() => result.current.onItemDragOver(FOLDER, over))

    expect(over.defaultPrevented).toBe(false)
  })

  it('ignores a drag that is not one of ours', () => {
    const { result } = setup()
    const over = dragEvent(['Files'])
    act(() => result.current.onItemDragOver(FOLDER, over))

    // An external file drag belongs to UploadDropzone, not to move.
    expect(over.defaultPrevented).toBe(false)
    expect(result.current.dropTargetId).toBeNull()
  })

  it('marks the folder under the cursor as the drop target', () => {
    const { result } = setup()
    act(() => result.current.onItemDragStart(FILE_A, dragEvent([])))
    act(() => result.current.onItemDragOver(FOLDER, dragEvent([DRAG_MIME])))
    expect(result.current.dropTargetId).toBe('folder-1')

    act(() => result.current.onItemDragLeave(FOLDER))
    expect(result.current.dropTargetId).toBeNull()
  })

  it('keeps the successful moves when one item fails', async () => {
    conflictOn = 'file-b'
    const { result } = setup(['file-a', 'file-b'])
    act(() => result.current.onItemDragStart(FILE_A, dragEvent([])))
    act(() =>
      result.current.onItemDrop(
        FOLDER,
        dragEvent([DRAG_MIME], JSON.stringify(['file-a', 'file-b'])),
      ),
    )

    await waitFor(() => expect(result.current.moveError).toBeTruthy())
    // file-a still moved; only the clashing one is reported.
    expect(moves).toEqual([{ id: 'file-a', parent: 'folder-1' }])
    expect(result.current.moveError).toContain('b.txt')
    expect(result.current.moveError).toContain('already exists')
  })
})


describe('drag image', () => {
  it('names every selected item, not just the one under the cursor', () => {
    // The browser's default drag image is the single element the drag began
    // on — picking up three files and seeing one is what this replaces.
    const { result } = setup(['file-a', 'file-b', 'folder-1'])
    act(() => result.current.onItemDragStart(FILE_A, dragEvent([])))

    const text = lastDragImage?.textContent ?? ''
    expect(text).toContain('3 items')
    expect(text).toContain('a.txt')
    expect(text).toContain('b.txt')
    expect(text).toContain('Target')
  })

  it('collapses a long selection to a count plus the first few', () => {
    const many = Array.from({ length: 9 }, (_, i) => item(`x${i}`, `file${i}.txt`, 'FILE'))
    useAuthStore.setState({ accessToken: 'test-token' })
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    const { result } = renderHook(
      () => useDragMove({ selectedIds: new Set(many.map((m) => m.id)), items: many }),
      {
        wrapper: ({ children }) => (
          <QueryClientProvider client={client}>{children}</QueryClientProvider>
        ),
      },
    )
    act(() => result.current.onItemDragStart(many[0]!, dragEvent([])))

    const text = lastDragImage?.textContent ?? ''
    expect(text).toContain('9 items')
    expect(text).toContain('+6 more')
  })

  it('shows just the name when a single item is dragged', () => {
    const { result } = setup()
    act(() => result.current.onItemDragStart(FILE_A, dragEvent([])))

    expect(lastDragImage?.textContent).toBe('a.txt')
  })

  it('leaves nothing behind in the document', async () => {
    // The ghost has to be attached for the browser to rasterise it, so the
    // hook parks it off-screen — it must not accumulate there.
    const { result } = setup(['file-a', 'file-b'])
    act(() => result.current.onItemDragStart(FILE_A, dragEvent([])))

    await waitFor(() =>
      expect(document.body.querySelectorAll('[aria-hidden="true"]')).toHaveLength(0),
    )
  })
})
