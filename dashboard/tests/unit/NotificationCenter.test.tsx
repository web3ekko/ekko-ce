import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'

import { useWebSocketStore } from '../../src/store/websocket'
import { notificationsApiService } from '../../src/services/notifications-api'

vi.mock('../../src/services/notifications-api', () => ({
  notificationsApiService: {
    getHistory: vi.fn(),
  },
}))

describe('NotificationCenter', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })
  })

  it('loads history when offline and empty', async () => {
    useWebSocketStore.setState({
      notifications: [],
      connectionState: 'disconnected',
      isConnected: false,
    })

    const historyItem = {
      notification_id: 'notif-1',
      alert_id: 'alert-1',
      alert_name: 'Alert Name',
      title: 'Alert Title',
      message: 'Received from 0x1234567890abcdef1234567890abcdef12345678',
      priority: 'normal',
      delivery_status: 'pending',
      channels_delivered: 0,
      channels_failed: 0,
      created_at: '2026-01-28T10:46:32',
    }

    vi.mocked(notificationsApiService.getHistory).mockResolvedValue({
      count: 1,
      results: [historyItem],
      has_more: false,
    })

    const user = userEvent.setup()

    const { NotificationCenter } = await import('../../src/components/notifications/NotificationCenter')

    render(
      <MantineProvider>
        <NotificationCenter />
      </MantineProvider>
    )

    await user.click(screen.getByLabelText('Notifications'))

    await waitFor(() => {
      expect(screen.getByText('Alert Title')).toBeInTheDocument()
      expect(screen.getByText('Received from 0x1234...5678')).toBeInTheDocument()
    })
  })
})
