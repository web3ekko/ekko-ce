import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'

import { WebhooksPage } from '../../src/pages/dashboard/WebhooksPage'
import { notificationsApiService } from '../../src/services/notifications-api'

const emptyResponse = {
  results: [],
  count: 0,
  next: null,
  previous: null,
  page: 1,
  page_size: 20,
  total_pages: 1,
}

describe('WebhooksPage', () => {
  it('shows an empty state when there are no webhooks', async () => {
    const getSpy = vi.spyOn(notificationsApiService, 'getChannels').mockResolvedValue(emptyResponse)

    render(
      <MantineProvider>
        <WebhooksPage />
      </MantineProvider>
    )

    expect(await screen.findByText('No webhook endpoints yet')).toBeInTheDocument()

    getSpy.mockRestore()
  })

  it('renders webhook cards from the API', async () => {
    const getSpy = vi.spyOn(notificationsApiService, 'getChannels').mockResolvedValue({
      ...emptyResponse,
      count: 1,
      results: [
        {
          id: 'webhook-1',
          owner_type: 'user',
          owner_id: 'user-1',
          channel_type: 'webhook',
          label: 'Ops Webhook',
          config: {
            url: 'https://example.com/webhook',
            method: 'POST',
          },
          enabled: true,
          verified: true,
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-01T00:00:00Z',
          last_used_at: '2025-01-02T00:00:00Z',
        },
      ],
    })

    render(
      <MantineProvider>
        <WebhooksPage />
      </MantineProvider>
    )

    expect(await screen.findByText('Ops Webhook')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText('verified')).toBeInTheDocument()
    expect(screen.getByText('POST')).toBeInTheDocument()

    getSpy.mockRestore()
  })
})
