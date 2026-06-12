import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('renders the initial cloud drive page', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Cloud Drive' })).toBeInTheDocument()
    expect(screen.getByText('Frontend online')).toBeInTheDocument()
  })
})
