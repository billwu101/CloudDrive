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
        onCopyLink={vi.fn()}
        onToggleStar={vi.fn()}
        onTrash={vi.fn()}
        onAssistantAction={onAssistantAction}
      />,
    )

    await userEvent.click(screen.getByRole('menuitem', { name: /inspect details/i }))

    expect(onAssistantAction).toHaveBeenCalledWith(action, MOCK_FILE)
    expect(onClose).toHaveBeenCalled()
  })
})
