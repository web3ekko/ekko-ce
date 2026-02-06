import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'

import { WalletCard } from '../../src/components/wallets/WalletCard'

describe('WalletCard', () => {
  it('renders the token logo for the wallet balance', () => {
    const wallet = {
      id: 'wallet-1',
      name: 'Treasury',
      address: '0x1234567890abcdef1234567890abcdef12345678',
      blockchain: 'ethereum',
      privacy: 'private',
      status: 'active',
      balance: {
        amount: '12.5',
        symbol: 'ETH',
        usd_value: 42000,
      },
    }

    render(
      <MantineProvider>
        <WalletCard
          wallet={wallet as any}
          onView={vi.fn()}
          onSync={vi.fn().mockResolvedValue(undefined)}
          onCopyAddress={vi.fn()}
        />
      </MantineProvider>
    )

    expect(screen.getByRole('img', { name: /eth token logo/i })).toBeInTheDocument()
  })
})
