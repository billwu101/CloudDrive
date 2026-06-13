/**
 * Tests for FileTable — item rendering and interaction handler wiring.
 */
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => cleanup())

import type { DriveItemResponse } from '@/api/types'
import { FileTable } from './FileTable'

function makeItem(overrides: Partial<DriveItemResponse> = {}): DriveItemResponse {
  return {
    id: 'item-1',
    owner_id: 'u1',
    parent_id: null,
    item_type: 'FILE',
    name: 'report.pdf',
    mime_type: 'application/pdf',
    extension: 'pdf',
    size_bytes: 204800,
    is_starred: false,
    is_deleted: false,
    deleted_at: null,
    created_by: 'u1',
    updated_by: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

const FOLDER = makeItem({ id: 'folder-1', item_type: 'FOLDER', name: 'My Docs', mime_type: null, extension: null, size_bytes: 0 })
const FILE1 = makeItem({ id: 'file-1', name: 'report.pdf' })
const FILE2 = makeItem({ id: 'file-2', name: 'photo.jpg', mime_type: 'image/jpeg', extension: 'jpg' })

function setup(
  items: DriveItemResponse[] = [FOLDER, FILE1, FILE2],
  selectedIds: Set<string> = new Set(),
) {
  const onItemClick = vi.fn()
  const onItemDoubleClick = vi.fn()
  const onItemContextMenu = vi.fn()
  const onStarClick = vi.fn()

  render(
    <FileTable
      items={items}
      selectedIds={selectedIds}
      onItemClick={onItemClick}
      onItemDoubleClick={onItemDoubleClick}
      onItemContextMenu={onItemContextMenu}
      onStarClick={onStarClick}
    />,
  )

  return { onItemClick, onItemDoubleClick, onItemContextMenu, onStarClick }
}

// ── 渲染 ──────────────────────────────────────────────────────────────────────

describe('rendering', () => {
  it('renders all item names', () => {
    setup()
    expect(screen.getByText('My Docs')).toBeInTheDocument()
    expect(screen.getByText('report.pdf')).toBeInTheDocument()
    expect(screen.getByText('photo.jpg')).toBeInTheDocument()
  })

  it('renders correct number of rows', () => {
    setup([FILE1, FILE2])
    // Two data rows in tbody (header is in thead)
    const rows = screen.getAllByRole('row')
    // rows includes header row + data rows
    expect(rows.length).toBeGreaterThanOrEqual(2)
  })

  it('renders empty table body when items array is empty', () => {
    setup([])
    // Header cells (th) still exist; no data cell (td) should be present
    const dataCells = document.querySelectorAll('tbody td')
    expect(dataCells.length).toBe(0)
  })

  it('renders table with header columns', () => {
    setup()
    expect(screen.getByText(/name/i)).toBeInTheDocument()
    expect(screen.getByText(/size/i)).toBeInTheDocument()
    expect(screen.getByText(/modified/i)).toBeInTheDocument()
  })
})

// ── 互動事件 ──────────────────────────────────────────────────────────────────

describe('click interactions', () => {
  it('calls onItemClick when row is clicked', async () => {
    const { onItemClick } = setup()
    await userEvent.click(screen.getByText('report.pdf'))
    expect(onItemClick).toHaveBeenCalled()
    expect(onItemClick.mock.calls[0][0]).toMatchObject({ id: 'file-1', name: 'report.pdf' })
  })

  it('calls onItemDoubleClick when row is double-clicked', async () => {
    const { onItemDoubleClick } = setup()
    await userEvent.dblClick(screen.getByText('My Docs'))
    expect(onItemDoubleClick).toHaveBeenCalled()
    expect(onItemDoubleClick.mock.calls[0][0]).toMatchObject({ id: 'folder-1' })
  })

  it('passes the correct item to onItemClick', async () => {
    const { onItemClick } = setup()
    await userEvent.click(screen.getByText('photo.jpg'))
    expect(onItemClick.mock.calls[0][0]).toMatchObject({ id: 'file-2', name: 'photo.jpg' })
  })
})
