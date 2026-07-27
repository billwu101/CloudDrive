import { useCallback, useState } from 'react'

import { isApiError } from '@/api/client'
import type { DriveItemResponse } from '@/api/types'

import { useMoveItem } from './useDrive'

/**
 * Dragging items onto a folder to move them (proposal §30).
 *
 * The custom MIME type is what keeps the app's three drag gestures apart:
 * `UploadDropzone` only reacts to `Files`, `useDragSelect` ignores anything
 * starting on a `[data-item-id]`, and the drop handling here only accepts
 * this type. Without it, dropping a desktop file on a folder would look
 * exactly like moving an item.
 */
export const DRAG_MIME = 'application/x-clouddrive-items'

export interface DragMove {
  /** Ids currently being dragged — used to dim them while in flight. */
  draggingIds: Set<string>
  /** Folder currently under the cursor and willing to accept the drop. */
  dropTargetId: string | null
  /** Names that could not be moved, with the reason. Cleared on the next drag. */
  moveError: string | null
  clearMoveError: () => void
  isMoving: boolean
  onItemDragStart: (item: DriveItemResponse, e: React.DragEvent) => void
  onItemDragEnd: () => void
  onItemDragOver: (item: DriveItemResponse, e: React.DragEvent) => void
  onItemDragLeave: (item: DriveItemResponse) => void
  onItemDrop: (item: DriveItemResponse, e: React.DragEvent) => void
}

interface UseDragMoveOptions {
  selectedIds: Set<string>
  items: DriveItemResponse[]
}

export function useDragMove({ selectedIds, items }: UseDragMoveOptions): DragMove {
  const move = useMoveItem()
  const [draggingIds, setDraggingIds] = useState<Set<string>>(new Set())
  const [dropTargetId, setDropTargetId] = useState<string | null>(null)
  const [moveError, setMoveError] = useState<string | null>(null)

  const onItemDragStart = useCallback(
    (item: DriveItemResponse, e: React.DragEvent) => {
      // Dragging something outside the selection moves only that item and
      // leaves the selection alone — a drag is a move gesture, not a
      // selection one (proposal §30.5 decision 2).
      const ids = selectedIds.has(item.id) ? [...selectedIds] : [item.id]
      setDraggingIds(new Set(ids))
      setMoveError(null)
      e.dataTransfer.effectAllowed = 'move'
      e.dataTransfer.setData(DRAG_MIME, JSON.stringify(ids))
    },
    [selectedIds],
  )

  const onItemDragEnd = useCallback(() => {
    setDraggingIds(new Set())
    setDropTargetId(null)
  }, [])

  const canAccept = useCallback(
    (item: DriveItemResponse, e: React.DragEvent) =>
      item.item_type === 'FOLDER' &&
      e.dataTransfer.types.includes(DRAG_MIME) &&
      !draggingIds.has(item.id),
    [draggingIds],
  )

  const onItemDragOver = useCallback(
    (item: DriveItemResponse, e: React.DragEvent) => {
      // Not calling preventDefault leaves the browser showing its "no drop"
      // cursor, which is exactly the feedback an invalid target should give.
      if (!canAccept(item, e)) return
      e.preventDefault()
      e.dataTransfer.dropEffect = 'move'
      setDropTargetId(item.id)
    },
    [canAccept],
  )

  const onItemDragLeave = useCallback((item: DriveItemResponse) => {
    setDropTargetId((current) => (current === item.id ? null : current))
  }, [])

  const onItemDrop = useCallback(
    (target: DriveItemResponse, e: React.DragEvent) => {
      if (!canAccept(target, e)) return
      e.preventDefault()
      e.stopPropagation()
      setDropTargetId(null)

      const raw = e.dataTransfer.getData(DRAG_MIME)
      let ids: string[]
      try {
        ids = JSON.parse(raw) as string[]
      } catch {
        return
      }
      const moving = ids.filter((id) => id !== target.id)
      if (moving.length === 0) return

      const nameOf = (id: string) => items.find((i) => i.id === id)?.name ?? id

      void (async () => {
        const failures: string[] = []
        // No bulk endpoint, and a name clash on one item is routine rather
        // than exceptional — so each move stands on its own and successes
        // are never rolled back (proposal §30.5 decision 3).
        for (const id of moving) {
          try {
            await move.mutateAsync({ id, targetParentId: target.id })
          } catch (err) {
            const reason = isApiError(err) ? err.message : 'could not be moved'
            failures.push(`${nameOf(id)} — ${reason}`)
          }
        }
        setDraggingIds(new Set())
        setMoveError(failures.length > 0 ? failures.join('; ') : null)
      })()
    },
    [canAccept, items, move],
  )

  return {
    draggingIds,
    dropTargetId,
    moveError,
    clearMoveError: () => setMoveError(null),
    isMoving: move.isPending,
    onItemDragStart,
    onItemDragEnd,
    onItemDragOver,
    onItemDragLeave,
    onItemDrop,
  }
}
