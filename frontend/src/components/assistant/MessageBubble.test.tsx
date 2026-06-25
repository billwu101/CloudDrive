import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MessageBubble } from './MessageBubble'

afterEach(() => cleanup())

describe('MessageBubble copy button', () => {
  it('shows a copy button for user messages and copies the content', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    render(<MessageBubble message={{ id: '1', role: 'user', content: 'List my files' }} />)

    const button = screen.getByRole('button', { name: /copy message/i })
    await userEvent.click(button)

    expect(writeText).toHaveBeenCalledWith('List my files')
    await waitFor(() => expect(screen.getByRole('button', { name: /copied/i })).toBeInTheDocument())

    vi.unstubAllGlobals()
  })

  it('does not render a copy button for assistant messages', () => {
    render(
      <MessageBubble message={{ id: '2', role: 'assistant', content: 'Here are your files.' }} />,
    )
    expect(screen.queryByRole('button', { name: /copy message/i })).not.toBeInTheDocument()
  })
})
