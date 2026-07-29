import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MOCK_FILE } from '@/test/handlers'
import {
  FileContextMenu,
  type AssistantContextMenuAction,
} from './FileContextMenu'

afterEach(() => cleanup())

describe('FileContextMenu', () => {
  it('renders assistant context menu actions from installed skill manifests', async () => {
    const action: AssistantContextMenuAction = {
      skillId: 'skill-1',
      label: 'Inspect details',
      handler: 'inspect_item_details',
    }
    const onAssistantAction = vi.fn()
    const onClose = vi.fn()

    render(
      <FileContextMenu
        item={MOCK_FILE}
        position={{ x: 10, y: 12 }}
        assistantActions={[action]}
        onClose={onClose}
        onPreview={vi.fn()}
        onRename={vi.fn()}
        onMove={vi.fn()}
        onShare={vi.fn()}
        onCopyName={vi.fn()}
        onToggleStar={vi.fn()}
        onTrash={vi.fn()}
        onAssistantAction={onAssistantAction}
      />,
    )

    await userEvent.click(screen.getByRole('menuitem', { name: /inspect details/i }))

    expect(onAssistantAction).toHaveBeenCalledWith(action, MOCK_FILE)
    expect(onClose).toHaveBeenCalled()
  })

  it('copies the file name via the Copy name item', async () => {
    const onCopyName = vi.fn()
    const onClose = vi.fn()

    render(
      <FileContextMenu
        item={MOCK_FILE}
        position={{ x: 0, y: 0 }}
        onClose={onClose}
        onPreview={vi.fn()}
        onRename={vi.fn()}
        onMove={vi.fn()}
        onShare={vi.fn()}
        onCopyName={onCopyName}
        onToggleStar={vi.fn()}
        onTrash={vi.fn()}
      />,
    )

    // The old "Copy link" was a dead no-op; the menu now offers the name.
    expect(screen.queryByRole('menuitem', { name: /copy link/i })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('menuitem', { name: /copy name/i }))

    expect(onCopyName).toHaveBeenCalledWith(MOCK_FILE)
    expect(onClose).toHaveBeenCalled()
  })

  it('opens sharing via the Share item', async () => {
    const onShare = vi.fn()
    const onClose = vi.fn()

    render(
      <FileContextMenu
        item={MOCK_FILE}
        position={{ x: 0, y: 0 }}
        onClose={onClose}
        onPreview={vi.fn()}
        onRename={vi.fn()}
        onMove={vi.fn()}
        onShare={onShare}
        onCopyName={vi.fn()}
        onToggleStar={vi.fn()}
        onTrash={vi.fn()}
      />,
    )

    await userEvent.click(screen.getByRole('menuitem', { name: /share/i }))

    expect(onShare).toHaveBeenCalledWith(MOCK_FILE)
    expect(onClose).toHaveBeenCalled()
  })
})
