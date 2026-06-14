import { useEffect, useRef, useState } from 'react'

export interface DragRect {
  x: number
  y: number
  width: number
  height: number
}

/**
 * Rubber-band (lasso) selection — Windows-Explorer-style.
 *
 * All listeners live on `window` so the hook works even when the container
 * is rendered conditionally (e.g. only after data loads). The container ref
 * is checked at event dispatch time, not at effect setup time.
 *
 * Behaviour:
 * - pointerdown on empty space inside the file-list container (not on a file
 *   item, checkbox, button, or link) → starts the drag
 * - pointermove > 5 px dead-zone → shows the selection rectangle and
 *   selects every [data-item-id] element whose bounding rect overlaps it
 * - pointerup after real movement → keeps the selection
 * - pointerup with no movement → clears the selection (click-on-empty)
 */
export function useDragSelect(
  containerRef: React.RefObject<HTMLElement | null>,
  onSelectIds: (ids: string[]) => void,
  onClear: () => void,
): { dragRect: DragRect | null } {
  const [dragRect, setDragRect] = useState<DragRect | null>(null)

  // Keep callbacks in refs so the single effect never needs to re-register
  const selectRef = useRef(onSelectIds)
  const clearRef = useRef(onClear)
  useEffect(() => { selectRef.current = onSelectIds }, [onSelectIds])
  useEffect(() => { clearRef.current = onClear }, [onClear])

  const startPos = useRef<{ x: number; y: number } | null>(null)
  const active = useRef(false)
  const moved = useRef(false)
  const lastKey = useRef('')

  useEffect(() => {
    const onPointerDown = (e: PointerEvent) => {
      const container = containerRef.current
      // Only left button and only inside the file area, not sidebar/toolbars.
      if (e.button !== 0) return
      if (!container || !container.contains(e.target as Node)) return
      // Don't hijack clicks on file items or interactive controls
      if ((e.target as Element).closest('[data-item-id], input, button, a, label, [role="button"]')) return

      // Stop the browser's native text-selection gesture before it begins.
      e.preventDefault()
      startPos.current = { x: e.clientX, y: e.clientY }
      active.current = true
      moved.current = false
      lastKey.current = ''
      window.getSelection()?.removeAllRanges()
    }

    const onPointerMove = (e: PointerEvent) => {
      if (!active.current || !startPos.current) return

      e.preventDefault()
      const dx = e.clientX - startPos.current.x
      const dy = e.clientY - startPos.current.y

      // Dead-zone: ignore tiny wobbles
      if (!moved.current && Math.abs(dx) < 5 && Math.abs(dy) < 5) return

      if (!moved.current) {
        moved.current = true
      }

      // Keep clearing selection on every move — the browser can re-create
      // it between ticks if the pointer passes over selectable text.
      window.getSelection()?.removeAllRanges()

      const rect: DragRect = {
        x: Math.min(startPos.current.x, e.clientX),
        y: Math.min(startPos.current.y, e.clientY),
        width: Math.abs(dx),
        height: Math.abs(dy),
      }
      setDragRect(rect)

      // Find items whose bounding box overlaps the selection rect
      const container = containerRef.current
      const ids: string[] = []
      if (container) {
        container.querySelectorAll<HTMLElement>('[data-item-id]').forEach((el) => {
          const r = el.getBoundingClientRect()
          if (r.right > rect.x && r.left < rect.x + rect.width &&
              r.bottom > rect.y && r.top < rect.y + rect.height) {
            if (el.dataset.itemId) ids.push(el.dataset.itemId)
          }
        })
      }

      // Avoid redundant store updates if selection hasn't changed
      const key = [...ids].sort().join(',')
      if (key !== lastKey.current) {
        lastKey.current = key
        selectRef.current(ids)
      }
    }

    const onSelectStart = (e: Event) => {
      if (active.current) e.preventDefault()
    }

    const onPointerUp = () => {
      if (!active.current) return

      active.current = false
      if (!moved.current) {
        // Was just a click on empty space → clear selection
        clearRef.current()
      }
      startPos.current = null
      moved.current = false
      lastKey.current = ''
      setDragRect(null)
    }

    window.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', onPointerUp)
    document.addEventListener('selectstart', onSelectStart)

    return () => {
      window.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      window.removeEventListener('pointercancel', onPointerUp)
      document.removeEventListener('selectstart', onSelectStart)
    }
  }, [containerRef])  // stable ref — runs once on mount

  return { dragRect }
}
