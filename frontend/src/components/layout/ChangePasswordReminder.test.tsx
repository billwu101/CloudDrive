import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { ChangePasswordReminder } from './ChangePasswordReminder'

afterEach(() => cleanup())

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ChangePasswordReminder />
    </MemoryRouter>,
  )
}

describe('ChangePasswordReminder', () => {
  it('shows a reminder with a link to settings', () => {
    renderAt('/drive')
    expect(screen.getByRole('alert')).toHaveTextContent(/password was reset/i)
    expect(screen.getByRole('link', { name: /change it now/i })).toHaveAttribute(
      'href',
      '/settings',
    )
  })

  it('hides itself on the settings page (no need to nag there)', () => {
    renderAt('/settings')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('can be dismissed', async () => {
    renderAt('/drive')
    await userEvent.click(screen.getByRole('button', { name: /dismiss reminder/i }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
