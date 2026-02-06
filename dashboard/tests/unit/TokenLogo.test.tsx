import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'

import { TokenLogo } from '../../src/components/brand/TokenLogo'

describe('TokenLogo', () => {
  it('renders a token logo container for known tokens', () => {
    render(
      <MantineProvider>
        <TokenLogo symbol="ETH" />
      </MantineProvider>
    )

    expect(screen.getByRole('img', { name: /eth token logo/i })).toBeInTheDocument()
  })

  it('renders fallback initials when no icon is found', () => {
    render(
      <MantineProvider>
        <TokenLogo symbol="ZZZ" />
      </MantineProvider>
    )

    expect(screen.getByText('ZZ')).toBeInTheDocument()
  })
})
