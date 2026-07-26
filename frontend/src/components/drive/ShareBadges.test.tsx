import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { ShareBadges } from './ShareBadges'

afterEach(() => cleanup())

describe('ShareBadges', () => {
  it('marks nothing when the item is private', () => {
    const { container } = render(
      <ShareBadges isSharedWithUsers={false} hasActivePublicLink={false} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('distinguishes people from a public link', () => {
    // The two must never collapse into one marker: a public link is the only
    // way in that needs no account (proposal §29.5 decision 2).
    render(<ShareBadges isSharedWithUsers hasActivePublicLink={false} />)
    expect(screen.getByLabelText('Shared with other people')).toBeInTheDocument()
    expect(screen.queryByLabelText('Has an active public link')).not.toBeInTheDocument()

    cleanup()
    render(<ShareBadges isSharedWithUsers={false} hasActivePublicLink />)
    expect(screen.queryByLabelText('Shared with other people')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Has an active public link')).toBeInTheDocument()
  })

  it('shows both when an item is shared both ways', () => {
    render(<ShareBadges isSharedWithUsers hasActivePublicLink />)
    expect(screen.getByLabelText('Shared with other people')).toBeInTheDocument()
    expect(screen.getByLabelText('Has an active public link')).toBeInTheDocument()
  })
})
