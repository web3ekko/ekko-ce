import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'

import { UserWalletGroupCard } from '../../src/components/wallets/UserWalletGroupCard'
import type { UserWalletGroup } from '../../src/services/groups-api'

describe('UserWalletGroupCard', () => {
  afterEach(() => {
    cleanup()
  })

  it('saves updated routing and switches', async () => {
    const user = userEvent.setup()

    const group: UserWalletGroup = {
      id: '11111111-1111-1111-1111-111111111111',
      user: 'u1',
      user_email: 'user@example.com',
      wallet_group: 'wg1',
      wallet_group_name: 'Provider Wallets',
      provider: 'p1',
      provider_name: 'provider@example.com',
      wallet_keys: ['ETH:mainnet:0xabc'],
      auto_subscribe_alerts: true,
      notification_routing: 'callback_only',
      access_control: {},
      is_active: true,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    const onUpdate = vi.fn().mockResolvedValue(undefined)

    render(
      <MantineProvider>
        <UserWalletGroupCard group={group} onUpdate={onUpdate} />
      </MantineProvider>
    )

    await user.click(screen.getByLabelText('Toggle provider wallet group details'))

    await user.click(screen.getByText('Both'))
    await user.click(screen.getByLabelText('Active'))

    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    expect(onUpdate).toHaveBeenCalledTimes(1)
    expect(onUpdate).toHaveBeenCalledWith(group.id, {
      notification_routing: 'both',
      auto_subscribe_alerts: true,
      is_active: false,
    })
  })

  it('calls onDisconnect when confirmed', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    const group: UserWalletGroup = {
      id: '22222222-2222-2222-2222-222222222222',
      user: 'u1',
      user_email: 'user@example.com',
      wallet_group: 'wg1',
      wallet_group_name: 'Provider Wallets',
      provider: 'p1',
      provider_name: 'provider@example.com',
      wallet_keys: ['ETH:mainnet:0xabc'],
      auto_subscribe_alerts: true,
      notification_routing: 'callback_only',
      access_control: {},
      is_active: true,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    const onUpdate = vi.fn().mockResolvedValue(undefined)
    const onDisconnect = vi.fn().mockResolvedValue(undefined)

    render(
      <MantineProvider>
        <UserWalletGroupCard group={group} onUpdate={onUpdate} onDisconnect={onDisconnect} />
      </MantineProvider>
    )

    await user.click(screen.getByLabelText('Disconnect provider wallet group'))

    expect(onDisconnect).toHaveBeenCalledTimes(1)
    expect(onDisconnect).toHaveBeenCalledWith(group.id)
  })

  it('adds and removes wallets when handlers are provided', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    const group: UserWalletGroup = {
      id: '33333333-3333-3333-3333-333333333333',
      user: 'u1',
      user_email: 'user@example.com',
      wallet_group: 'wg1',
      wallet_group_name: 'Provider Wallets',
      provider: 'p1',
      provider_name: 'provider@example.com',
      wallet_keys: ['ETH:mainnet:0xabc'],
      auto_subscribe_alerts: true,
      notification_routing: 'callback_only',
      access_control: {},
      is_active: true,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    const onUpdate = vi.fn().mockResolvedValue(undefined)
    const onAddWallets = vi.fn().mockResolvedValue(undefined)
    const onRemoveWallet = vi.fn().mockResolvedValue(undefined)

    render(
      <MantineProvider>
        <UserWalletGroupCard
          group={group}
          onUpdate={onUpdate}
          onAddWallets={onAddWallets}
          onRemoveWallet={onRemoveWallet}
        />
      </MantineProvider>
    )

    await user.click(screen.getByLabelText('Toggle provider wallet group details'))

    await user.type(screen.getByLabelText('Add wallet key'), 'ETH:mainnet:0xdef')
    await user.click(screen.getByRole('button', { name: 'Add' }))

    expect(onAddWallets).toHaveBeenCalledWith(group.id, ['ETH:mainnet:0xdef'])

    await user.click(screen.getByLabelText('Remove wallet from provider group'))

    expect(onRemoveWallet).toHaveBeenCalledWith(group.id, 'ETH:mainnet:0xabc')
  })
})
