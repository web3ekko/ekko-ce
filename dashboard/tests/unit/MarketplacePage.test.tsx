import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { MemoryRouter } from 'react-router-dom'
import { notifications } from '@mantine/notifications'

import { MarketplacePage } from '../../src/pages/marketplace/MarketplacePage'
import { alertsApiService } from '../../src/services/alerts-api'

describe('MarketplacePage', () => {
  it('renders templates from the API and opens the alert builder on use', async () => {
    const user = userEvent.setup()
    if (typeof globalThis.localStorage?.clear !== 'function') {
      const store = new Map<string, string>()
      globalThis.localStorage = {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => {
          store.set(key, value)
        },
        removeItem: (key: string) => {
          store.delete(key)
        },
        clear: () => {
          store.clear()
        },
        key: (index: number) => Array.from(store.keys())[index] ?? null,
        get length() {
          return store.size
        },
      } as Storage
    }
    globalThis.localStorage.clear()
    const listTemplatesSpy = vi.spyOn(alertsApiService, 'listTemplates').mockResolvedValue({
      results: [
        {
          id: 'tpl-1',
          fingerprint: 'sha256:abc',
          name: 'Treasury Balance Template',
          description: 'Monitor treasury balance thresholds',
          target_kind: 'wallet',
          is_public: true,
          is_verified: false,
          latest_template_version: 3,
          usage_count: 24,
          variable_names: ['threshold'],
          scope_networks: ['ETH:mainnet'],
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-01T00:00:00Z',
        },
      ],
      count: 1,
      next: null,
      previous: null,
      page: 1,
      page_size: 30,
      total_pages: 1,
    })
    const notifySpy = vi.spyOn(notifications, 'show').mockImplementation(() => undefined)

    render(
      <MantineProvider>
        <MemoryRouter>
          <MarketplacePage />
        </MemoryRouter>
      </MantineProvider>
    )

    expect(await screen.findByText('Marketplace')).toBeInTheDocument()

    expect(await screen.findByText('Treasury Balance Template')).toBeInTheDocument()

    const useButton = await screen.findByRole('button', { name: 'Use template' })
    await user.click(useButton)

    expect(notifySpy).toHaveBeenCalled()

    listTemplatesSpy.mockRestore()
    notifySpy.mockRestore()
  })
})
