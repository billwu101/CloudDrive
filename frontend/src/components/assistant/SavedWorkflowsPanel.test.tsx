import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AssistantSavedWorkflowResponse } from '@/api/types'
import { SavedWorkflowsPanel } from './SavedWorkflowsPanel'

const workflow: AssistantSavedWorkflowResponse = {
  id: 'wf-1',
  name: 'Tidy downloads',
  source_nl: 'organize my downloads',
  steps: [
    {
      index: 0,
      skill: 'organize_by_type',
      arguments: {},
      depends_on: [],
      permission_tier: 'write',
      requires_approval: true,
    },
  ],
  created_at: '2024-01-01T00:00:00Z',
}

afterEach(() => cleanup())

describe('SavedWorkflowsPanel', () => {
  it('renders nothing when there are no saved workflows', () => {
    const { container } = render(
      <SavedWorkflowsPanel workflows={[]} rerunningId={null} onRerun={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('lists saved workflows and re-runs one on click', async () => {
    const onRerun = vi.fn()
    render(<SavedWorkflowsPanel workflows={[workflow]} rerunningId={null} onRerun={onRerun} />)

    expect(screen.getByText('Tidy downloads')).toBeInTheDocument()
    expect(screen.getByText('1 step')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /run/i }))
    expect(onRerun).toHaveBeenCalledWith('wf-1')
  })

  it('disables the run button for the workflow currently re-running', () => {
    render(<SavedWorkflowsPanel workflows={[workflow]} rerunningId="wf-1" onRerun={vi.fn()} />)
    expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
  })
})
