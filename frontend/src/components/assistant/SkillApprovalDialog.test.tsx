import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AssistantSkillResponse } from '@/api/types'
import { SkillApprovalDialog } from './SkillApprovalDialog'

const skill: AssistantSkillResponse = {
  id: 'skill-1',
  name: 'decompress_7z',
  description: 'Extract a 7z or zip archive.',
  manifest: {
    name: 'decompress_7z',
    description: 'Extract a 7z or zip archive.',
    version: '1.0.0',
    ui: {
      context_menu: [{ label: 'Extract here', handler: 'decompress_7z', item_types: ['FILE'] }],
    },
  },
  code: 'def run(input_path, output_dir, params):\n    return {"ok": True}\n',
  status: 'pending',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

afterEach(() => cleanup())

describe('SkillApprovalDialog', () => {
  it('renders the full generated code for review', () => {
    render(
      <SkillApprovalDialog
        skill={skill}
        loading={false}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByLabelText(/generated skill code/i)).toHaveTextContent(
      'def run(input_path, output_dir, params)',
    )
    expect(screen.getByText(/Adds "Extract here" to FILE/)).toBeInTheDocument()
  })

  it('approves and rejects through the action buttons', async () => {
    const onApprove = vi.fn()
    const onReject = vi.fn()
    render(
      <SkillApprovalDialog
        skill={skill}
        loading={false}
        onApprove={onApprove}
        onReject={onReject}
        onClose={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /approve & install/i }))
    expect(onApprove).toHaveBeenCalledWith(skill)

    await userEvent.click(screen.getByRole('button', { name: /reject/i }))
    expect(onReject).toHaveBeenCalled()
  })

  it('renders nothing when there is no skill', () => {
    const { container } = render(
      <SkillApprovalDialog
        skill={null}
        loading={false}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
