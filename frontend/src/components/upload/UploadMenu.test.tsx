import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { UploadMenu } from './UploadMenu'

afterEach(() => cleanup())

describe('UploadMenu', () => {
  it('is a single Upload button (no dropdown menu)', () => {
    render(<UploadMenu onFiles={vi.fn()} />)
    expect(screen.getByRole('button', { name: /upload/i })).toBeInTheDocument()
    // Simplified to one action — no menu, no separate folder option.
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem')).not.toBeInTheDocument()
  })

  it('opens a plain multi-file picker (folders go through drag-and-drop)', () => {
    const { container } = render(<UploadMenu onFiles={vi.fn()} />)
    const inputs = container.querySelectorAll('input[type="file"]')
    expect(inputs).toHaveLength(1)
    const input = inputs[0] as HTMLInputElement
    expect(input.multiple).toBe(true)
    expect(input.hasAttribute('webkitdirectory')).toBe(false)
  })

  it('forwards selected files to onFiles', () => {
    const onFiles = vi.fn()
    const { container } = render(<UploadMenu onFiles={onFiles} />)
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(fileInput, {
      target: { files: [new File(['x'], 'a.txt', { type: 'text/plain' })] },
    })
    expect(onFiles).toHaveBeenCalledTimes(1)
    expect(onFiles.mock.calls[0][0][0].name).toBe('a.txt')
  })
})
