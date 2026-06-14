import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useRef, useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useDragSelect } from './useDragSelect'

afterEach(() => {
  cleanup()
  document.body.style.userSelect = ''
})

function rect(left: number, top: number, width: number, height: number): DOMRect {
  return {
    x: left,
    y: top,
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    toJSON: () => ({}),
  }
}

function Harness({
  initialSelection = [],
  onClear = vi.fn(),
}: {
  initialSelection?: string[]
  onClear?: () => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedIds, setSelectedIds] = useState(new Set(initialSelection))
  const { dragRect } = useDragSelect(
    containerRef,
    (ids) => setSelectedIds(new Set(ids)),
    onClear,
  )

  return (
    <>
      <div ref={containerRef} data-testid="container">
        <div
          data-item-id="folder-1"
          data-testid="folder-1"
          aria-selected={selectedIds.has('folder-1')}
        />
        <div
          data-item-id="file-1"
          data-testid="file-1"
          aria-selected={selectedIds.has('file-1')}
        />
        <button data-testid="button">Action</button>
      </div>
      {dragRect && (
        <div
          data-testid="drag-overlay"
          style={{
            left: dragRect.x,
            top: dragRect.y,
            width: dragRect.width,
            height: dragRect.height,
          }}
        />
      )}
    </>
  )
}

function setItemRects() {
  vi.spyOn(screen.getByTestId('folder-1'), 'getBoundingClientRect')
    .mockReturnValue(rect(20, 20, 80, 80))
  vi.spyOn(screen.getByTestId('file-1'), 'getBoundingClientRect')
    .mockReturnValue(rect(120, 20, 80, 80))
}

describe('useDragSelect', () => {
  it('selects every file or folder intersecting the drag rectangle', () => {
    render(<Harness />)
    setItemRects()

    fireEvent.pointerDown(screen.getByTestId('container'), {
      button: 0,
      clientX: 10,
      clientY: 10,
    })
    fireEvent.pointerMove(window, { clientX: 210, clientY: 110 })

    expect(screen.getByTestId('drag-overlay')).toHaveStyle({
      left: '10px',
      top: '10px',
      width: '200px',
      height: '100px',
    })
    expect(screen.getByTestId('folder-1')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('file-1')).toHaveAttribute('aria-selected', 'true')

    fireEvent.pointerUp(window)
    expect(screen.queryByTestId('drag-overlay')).not.toBeInTheDocument()
  })

  it('replaces the previous selection during a regular drag', () => {
    render(<Harness initialSelection={['old-item']} />)
    setItemRects()

    fireEvent.pointerDown(screen.getByTestId('container'), {
      button: 0,
      clientX: 10,
      clientY: 10,
    })
    fireEvent.pointerMove(window, { clientX: 105, clientY: 105 })

    expect(screen.getByTestId('folder-1')).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('file-1')).toHaveAttribute('aria-selected', 'false')
  })

  it('clears selection when empty space is clicked without dragging', () => {
    const onClear = vi.fn()
    render(<Harness initialSelection={['folder-1']} onClear={onClear} />)

    fireEvent.pointerDown(screen.getByTestId('container'), {
      button: 0,
      clientX: 10,
      clientY: 10,
    })
    fireEvent.pointerUp(window)

    expect(onClear).toHaveBeenCalledOnce()
  })

  it('does not start selection from a file item or interactive control', () => {
    render(<Harness />)
    setItemRects()

    fireEvent.pointerDown(screen.getByTestId('folder-1'), {
      button: 0,
      clientX: 30,
      clientY: 30,
    })
    fireEvent.pointerMove(window, { clientX: 210, clientY: 110 })
    expect(screen.queryByTestId('drag-overlay')).not.toBeInTheDocument()

    fireEvent.pointerDown(screen.getByTestId('button'), {
      button: 0,
      clientX: 10,
      clientY: 10,
    })
    fireEvent.pointerMove(window, { clientX: 210, clientY: 110 })
    expect(screen.queryByTestId('drag-overlay')).not.toBeInTheDocument()
  })

  it('ignores movement inside the five-pixel dead zone', () => {
    render(<Harness />)

    fireEvent.pointerDown(screen.getByTestId('container'), {
      button: 0,
      clientX: 10,
      clientY: 10,
    })
    fireEvent.pointerMove(window, { clientX: 14, clientY: 14 })

    expect(screen.queryByTestId('drag-overlay')).not.toBeInTheDocument()
    expect(document.body.style.userSelect).toBe('')

    act(() => fireEvent.pointerUp(window))
  })
})
