import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'

import { ChainLogo } from '../../src/components/brand/ChainLogo'

describe('ChainLogo', () => {
  it('renders the chain logo image when known', () => {
    render(
      <MantineProvider>
        <ChainLogo chain="ethereum" />
      </MantineProvider>
    )

    const logo = screen.getByRole('img', { name: /ethereum logo/i })
    expect(logo).toBeInTheDocument()
    expect(logo.querySelector('svg')).not.toBeNull()
  })

  it('renders initials fallback when chain is unknown', () => {
    render(
      <MantineProvider>
        <ChainLogo chain="unknown" />
      </MantineProvider>
    )

    expect(screen.getByText('CH')).toBeInTheDocument()
  })
})
