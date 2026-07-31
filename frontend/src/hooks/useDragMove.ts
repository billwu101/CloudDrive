import { useCallback, useState } from 'react'

import { isApiError } from '@/api/client'
import type { BrowsableItem } from '@/api/types'

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

/** Names listed in full on the drag image before it collapses to "+N more". */
const GHOST_NAMES = 3

/**
 * Builds the image dragged under the cursor.
 *
 * The browser's default is a snapshot of the one element the drag started on,
 * which is actively misleading for a multi-selection: you pick up eight files
 * and the cursor shows one. This shows the count and names so it is obvious
 * what is about to move.
 *
 * The node has to be in the document for the browser to rasterise it, so it is
 * parked off-screen and removed once the snapshot has been taken.
 */
function makeDragGhost(names: string[]): HTMLElement {
  const ghost = document.createElement('div')
  ghost.setAttribute('aria-hidden', 'true')
  ghost.style.cssText = [
    'position:fixed',
    'top:-10000px',
    'left:-10000px',
    'pointer-events:none',
    'display:inline-block',
    'min-width:160px',
    'max-width:280px',
    'padding:8px 10px',
    'border:1px solid rgba(0,0,0,0.12)',
    'border-radius:8px',
    'background:#fff',
    'box-shadow:0 6px 16px rgba(0,0,0,0.18), 4px 4px 0 -1px #fff, 5px 5px 0 -1px rgba(0,0,0,0.12)',
    'font:500 12px/1.5 system-ui,-apple-system,sans-serif',
    'color:#111',
  ].join(';')

  const heading = document.createElement('div')
  heading.textContent = names.length === 1 ? names[0]! : `${names.length} items`
  heading.style.cssText = 'font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'
  ghost.appendChild(heading)

  if (names.length > 1) {
    for (const name of names.slice(0, GHOST_NAMES)) {
      const row = document.createElement('div')
      row.textContent = name
      row.style.cssText =
        'color:#555;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:400'
      ghost.appendChild(row)
    }
    if (names.length > GHOST_NAMES) {
      const more = document.createElement('div')
      more.textContent = `+${names.length - GHOST_NAMES} more`
      more.style.cssText = 'color:#888;font-weight:400'
      ghost.appendChild(more)
    }
  }

  document.body.appendChild(ghost)
  return ghost
}

export interface DragMove {
  /** Ids currently being dragged — used to dim them while in flight. */
  draggingIds: Set<string>
  /** Folder currently under the cursor and willing to accept the drop. */
  dropTargetId: string | null
  /** Names that could not be moved, with the reason. Cleared on the next drag. */
  moveError: string | null
  clearMoveError: () => void
  isMoving: boolean
  onItemDragStart: (item: BrowsableItem, e: React.DragEvent) => void
  onItemDragEnd: () => void
  onItemDragOver: (item: BrowsableItem, e: React.DragEvent) => void
  onItemDragLeave: (item: BrowsableItem) => void
  onItemDrop: (item: BrowsableItem, e: React.DragEvent) => void
}

interface UseDragMoveOptions {
  selectedIds: Set<string>
  items: BrowsableItem[]
  /**
   * How to actually move one item. Guests go through the public endpoint with
   * their share credential; left out, this is the signed-in drive mutation.
   */
  moveItem?: (id: string, targetParentId: string) => Promise<unknown>
}

export function useDragMove({ selectedIds, items, moveItem }: UseDragMoveOptions): DragMove {
  const move = useMoveItem()
  const [draggingIds, setDraggingIds] = useState<Set<string>>(new Set())
  const [dropTargetId, setDropTargetId] = useState<string | null>(null)
  const [moveError, setMoveError] = useState<string | null>(null)
  const [isMoving, setIsMoving] = useState(false)

  const onItemDragStart = useCallback(
    (item: BrowsableItem, e: React.DragEvent) => {
      // Dragging something outside the selection moves only that item and
      // leaves the selection alone — a drag is a move gesture, not a
      // selection one (proposal §30.5 decision 2).
      const ids = selectedIds.has(item.id) ? [...selectedIds] : [item.id]
      setDraggingIds(new Set(ids))
      setMoveError(null)
      e.dataTransfer.effectAllowed = 'move'
      e.dataTransfer.setData(DRAG_MIME, JSON.stringify(ids))

      // Keep the drag image in the same order as the listing, so it reads like
      // what the user just selected rather than an arbitrary set.
      const names = items.filter((i) => ids.includes(i.id)).map((i) => i.name)
      if (typeof e.dataTransfer.setDragImage === 'function' && names.length > 0) {
        const ghost = makeDragGhost(names)
        e.dataTransfer.setDragImage(ghost, 12, 12)
        // The browser rasterises during this event; drop the node right after.
        setTimeout(() => ghost.remove(), 0)
      }
    },
    [selectedIds, items],
  )

  const onItemDragEnd = useCallback(() => {
    setDraggingIds(new Set())
    setDropTargetId(null)
  }, [])

  const canAccept = useCallback(
    (item: BrowsableItem, e: React.DragEvent) =>
      item.item_type === 'FOLDER' &&
      e.dataTransfer.types.includes(DRAG_MIME) &&
      !draggingIds.has(item.id),
    [draggingIds],
  )

  const onItemDragOver = useCallback(
    (item: BrowsableItem, e: React.DragEvent) => {
      // Not calling preventDefault leaves the browser showing its "no drop"
      // cursor, which is exactly the feedback an invalid target should give.
      if (!canAccept(item, e)) return
      e.preventDefault()
      e.dataTransfer.dropEffect = 'move'
      setDropTargetId(item.id)
    },
    [canAccept],
  )

  const onItemDragLeave = useCallback((item: BrowsableItem) => {
    setDropTargetId((current) => (current === item.id ? null : current))
  }, [])

  const onItemDrop = useCallback(
    (target: BrowsableItem, e: React.DragEvent) => {
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

      const runMove =
        moveItem ?? ((id: string, parentId: string) => move.mutateAsync({ id, targetParentId: parentId }))

      void (async () => {
        const failures: string[] = []
        setIsMoving(true)
        // No bulk endpoint, and a name clash on one item is routine rather
        // than exceptional — so each move stands on its own and successes
        // are never rolled back (proposal §30.5 decision 3).
        for (const id of moving) {
          try {
            await runMove(id, target.id)
          } catch (err) {
            const reason = isApiError(err) ? err.message : 'could not be moved'
            failures.push(`${nameOf(id)} — ${reason}`)
          }
        }
        setIsMoving(false)
        setDraggingIds(new Set())
        setMoveError(failures.length > 0 ? failures.join('; ') : null)
      })()
    },
    [canAccept, items, move, moveItem],
  )

  return {
    draggingIds,
    dropTargetId,
    moveError,
    clearMoveError: () => setMoveError(null),
    isMoving,
    onItemDragStart,
    onItemDragEnd,
    onItemDragOver,
    onItemDragLeave,
    onItemDrop,
  }
}
