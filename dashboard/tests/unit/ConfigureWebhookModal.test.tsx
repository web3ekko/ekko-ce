import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { notifications } from '@mantine/notifications'

import { ConfigureWebhookModal } from '../../src/components/notifications/ConfigureWebhookModal'
import { notificationsApiService } from '../../src/services/notifications-api'

const createWebhookResponse = {
  id: 'webhook-1',
  owner_type: 'user' as const,
  owner_id: 'user-1',
  channel_type: 'webhook' as const,
  label: 'Ops Webhook',
  config: {
    url: 'https://example.com/webhook',
    method: 'POST',
    headers: {},
  },
  enabled: true,
  verified: false,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

describe('ConfigureWebhookModal', () => {
  it('creates a webhook channel from form input', async () => {
    const user = userEvent.setup()
    const createSpy = vi
      .spyOn(notificationsApiService, 'createWebhookChannel')
      .mockResolvedValue(createWebhookResponse)
    const notifySpy = vi.spyOn(notifications, 'show').mockImplementation(() => undefined)
    const onSaved = vi.fn()
    const onClose = vi.fn()

    render(
      <MantineProvider>
        <ConfigureWebhookModal opened onClose={onClose} onSaved={onSaved} />
      </MantineProvider>
    )

    await user.type(screen.getByLabelText(/name/i), 'Ops Webhook')
    await user.type(screen.getByLabelText(/endpoint url/i), 'https://example.com/webhook')

    await user.click(screen.getByRole('button', { name: 'Save Webhook' }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith({
        label: 'Ops Webhook',
        url: 'https://example.com/webhook',
        method: 'POST',
        headers: {},
        secret: undefined,
      })
      expect(onSaved).toHaveBeenCalledWith(createWebhookResponse)
    })

    createSpy.mockRestore()
    notifySpy.mockRestore()
  })
})
