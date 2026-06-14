import { useCallback, useEffect, useRef, useState } from 'react'

export interface DragRect {
  x: number
  y: number
  width: number
  height: number
}

/**
 * Rubber-band (lasso) selection.
 *
 * - pointerdown on empty space starts a drag.
 * - During drag, calls onSelectIds with every [data-item-id] element whose
 *   bounding rect overlaps the selection rectangle.
 * - pointerup with no movement (< 5 px) is treated as a click → calls onClear.
 * - pointerup after drag keeps the selection and calls onSelectIds one final time.
 *
 * The caller is responsible for rendering the visual rectangle using dragRect.
 */
export function useDragSelect(
  containerRef: React.RefObject<HTMLElement | null>,
  onSelectIds: (ids: string[]) => void,
  onClear: () => void,
): { dragRect: DragRect | null } {
  const [dragRect, setDragRect] = useState<DragRect | null>(null)

  const startPos = useRef<{ x: number; y: number } | null>(null)
  const isDragging = useRef(false)
  const hasMoved = useRef(false)
  const lastKey = useRef('')

  // Stable wrapper so the effect doesn't re-run when the component re-renders
  const selectRef = useRef(onSelectIds)
  const clearRef = useRef(onClear)
  useEffect(() => { selectRef.current = onSelectIds }, [onSelectIds])
  useEffect(() => { clearRef.current = onClear }, [onClear])

  const getIntersecting = useCallback((rect: DragRect): string[] => {
    const container = containerRef.current
    if (!container) return []
    const ids: string[] = []
    container.querySelectorAll<HTMLElement>('[data-item-id]').forEach((el) => {
      const r = el.getBoundingClientRect()
      if (r.right > rect.x && r.left < rect.x + rect.width &&
          r.bottom > rect.y && r.top < rect.y + rect.height) {
        if (el.dataset.itemId) ids.push(el.dataset.itemId)
      }
    })
    return ids
  }, [containerRef])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return
      // Only start drag on empty space, not on interactive items
      if ((e.target as Element).closest('[data-item-id]')) return
      startPos.current = { x: e.clientX, y: e.clientY }
      isDragging.current = true
      hasMoved.current = false
      lastKey.current = ''
    }

    const onPointerMove = (e: PointerEvent) => {
      if (!isDragging.current || !startPos.current) return

      const dx = e.clientX - startPos.current.x
      const dy = e.clientY - startPos.current.y

      // Dead-zone to avoid triggering on accidental micro-movements
      if (!hasMoved.current && Math.abs(dx) < 5 && Math.abs(dy) < 5) return
      hasMoved.current = true

      const rect: DragRect = {
        x: Math.min(startPos.current.x, e.clientX),
        y: Math.min(startPos.current.y, e.clientY),
        width: Math.abs(dx),
        height: Math.abs(dy),
      }
      setDragRect(rect)

      const ids = getIntersecting(rect)
      const key = [...ids].sort().join(',')
      if (key !== lastKey.current) {
        lastKey.current = key
        selectRef.current(ids)
      }
    }

    const onPointerUp = () => {
      if (!isDragging.current) return
      isDragging.current = false

      if (!hasMoved.current) {
        // Treat as a click on empty space → clear selection
        clearRef.current()
      }

      startPos.current = null
      hasMoved.current = false
      lastKey.current = ''
      setDragRect(null)
    }

    container.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', onPointerUp)

    return () => {
      container.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      window.removeEventListener('pointercancel', onPointerUp)
    }
  }, [containerRef, getIntersecting])

  return { dragRect }
}
