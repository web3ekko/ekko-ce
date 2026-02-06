import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { AlertDetailPage } from '../../src/pages/dashboard/AlertDetailPage'
import { httpClient } from '../../src/services/http-client'

vi.mock('../../src/services/http-client', () => ({
  httpClient: {
    get: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('AlertDetailPage', () => {
  it('wraps long alert titles', async () => {
    const longName =
      'Alert me if my wallet has more than 2 transactions in the last 24 hours on Ethereum'

    vi.mocked(httpClient.get).mockResolvedValue({
      data: {
        id: 'alert-1',
        name: longName,
        nl_description: 'Test description',
        enabled: true,
        event_type: 'ACCOUNT_EVENT',
        sub_event: 'CUSTOM',
        alert_type: 'wallet',
        target_group: null,
        target_group_name: null,
        target_group_type: null,
        target_keys: ['ETH:mainnet:0x1234567890abcdef1234567890abcdef12345678'],
        processing_status: 'skipped',
        created_at: '2026-01-28T00:00:00Z',
        updated_at: '2026-01-28T01:00:00Z',
        chains: ['ethereum'],
      },
    })

    render(
      <MantineProvider>
        <MemoryRouter initialEntries={['/dashboard/alerts/alert-1']}>
          <Routes>
            <Route path="/dashboard/alerts/:id" element={<AlertDetailPage />} />
          </Routes>
        </MemoryRouter>
      </MantineProvider>
    )

    const title = await screen.findByText(longName)
    expect(title).toHaveStyle('white-space: normal')
    expect(title).toHaveStyle('word-break: break-word')

    const description = await screen.findByText('Test description')
    expect(description).toHaveStyle('white-space: normal')
    expect(description).toHaveStyle('word-break: break-word')
  })
})
