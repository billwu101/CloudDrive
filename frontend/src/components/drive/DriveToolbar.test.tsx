/**
 * Tests for DriveToolbar — toolbar button visibility and click handler wiring.
 */
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => cleanup())

import { DriveToolbar } from './DriveToolbar'

function setup(selectedCount = 0) {
  const onNewFolder = vi.fn()
  const onTrashSelected = vi.fn()
  render(
    <DriveToolbar
      selectedCount={selectedCount}
      onNewFolder={onNewFolder}
      onTrashSelected={onTrashSelected}
    />,
  )
  return { onNewFolder, onTrashSelected }
}

// ── New Folder 按鈕 ───────────────────────────────────────────────────────────

describe('New Folder button', () => {
  it('is always visible regardless of selection count', () => {
    setup(0)
    expect(screen.getByRole('button', { name: /new folder/i })).toBeInTheDocument()
  })

  it('remains visible when items are selected', () => {
    setup(3)
    expect(screen.getByRole('button', { name: /new folder/i })).toBeInTheDocument()
  })

  it('calls onNewFolder when clicked', async () => {
    const { onNewFolder } = setup(0)
    await userEvent.click(screen.getByRole('button', { name: /new folder/i }))
    expect(onNewFolder).toHaveBeenCalledOnce()
  })
})

// ── Trash 按鈕 ────────────────────────────────────────────────────────────────

describe('Trash button', () => {
  it('is NOT visible when no items are selected', () => {
    setup(0)
    expect(screen.queryByRole('button', { name: /trash/i })).not.toBeInTheDocument()
  })

  it('appears when one item is selected', () => {
    setup(1)
    expect(screen.getByRole('button', { name: /trash/i })).toBeInTheDocument()
  })

  it('appears when multiple items are selected', () => {
    setup(5)
    expect(screen.getByRole('button', { name: /trash/i })).toBeInTheDocument()
  })

  it('shows the selected count in the button label', () => {
    setup(3)
    expect(screen.getByRole('button', { name: /trash.*3/i })).toBeInTheDocument()
  })

  it('calls onTrashSelected when clicked', async () => {
    const { onTrashSelected } = setup(2)
    await userEvent.click(screen.getByRole('button', { name: /trash/i }))
    expect(onTrashSelected).toHaveBeenCalledOnce()
  })

  it('does not call onNewFolder when trash button is clicked', async () => {
    const { onNewFolder } = setup(1)
    await userEvent.click(screen.getByRole('button', { name: /trash/i }))
    expect(onNewFolder).not.toHaveBeenCalled()
  })
})
