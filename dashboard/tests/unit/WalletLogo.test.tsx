import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'

import { WalletLogo } from '../../src/components/brand/WalletLogo'

describe('WalletLogo', () => {
  it('renders a wallet logo container for known wallets', () => {
    render(
      <MantineProvider>
        <WalletLogo name="MetaMask" />
      </MantineProvider>
    )

    expect(screen.getByRole('img', { name: /metamask wallet logo/i })).toBeInTheDocument()
  })

  it('renders fallback initials when no icon is found', () => {
    render(
      <MantineProvider>
        <WalletLogo name="Unknown Wallet" />
      </MantineProvider>
    )

    expect(screen.getByText('UN')).toBeInTheDocument()
  })
})
