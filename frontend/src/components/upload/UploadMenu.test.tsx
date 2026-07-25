import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { UploadMenu } from './UploadMenu'

afterEach(() => cleanup())

describe('UploadMenu', () => {
  it('opens a menu with file and folder options', async () => {
    render(<UploadMenu onFiles={vi.fn()} onFolders={vi.fn()} />)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /upload/i }))
    expect(screen.getByRole('menuitem', { name: /upload files/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /upload folder/i })).toBeInTheDocument()
  })

  it('the folder input is a directory picker', () => {
    const { container } = render(<UploadMenu onFiles={vi.fn()} onFolders={vi.fn()} />)
    const inputs = container.querySelectorAll('input[type="file"]')
    expect(inputs).toHaveLength(2)
    expect(Array.from(inputs).some((i) => i.hasAttribute('webkitdirectory'))).toBe(true)
  })

  it('forwards selected files to onFiles', () => {
    const onFiles = vi.fn()
    const { container } = render(<UploadMenu onFiles={onFiles} onFolders={vi.fn()} />)
    const fileInput = container.querySelector(
      'input[type="file"]:not([webkitdirectory])',
    ) as HTMLInputElement
    fireEvent.change(fileInput, {
      target: { files: [new File(['x'], 'a.txt', { type: 'text/plain' })] },
    })
    expect(onFiles).toHaveBeenCalledTimes(1)
    expect(onFiles.mock.calls[0][0][0].name).toBe('a.txt')
  })
})
