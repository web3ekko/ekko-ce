import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useSimpleAlerts } from '../../src/store/simple-alerts'

const mockGetAlerts = vi.fn()
const mockGetHistory = vi.fn()

vi.mock('../../src/services/alerts-api', () => ({
  default: {
    getAlerts: (...args: unknown[]) => mockGetAlerts(...args),
  },
}))

vi.mock('../../src/services/notifications-api', () => ({
  default: {
    getHistory: (...args: unknown[]) => mockGetHistory(...args),
  },
}))

describe('useSimpleAlerts', () => {
  beforeEach(() => {
    useSimpleAlerts.setState({
      alerts: [],
      selectedAlerts: [],
      isLoading: false,
      error: null,
      previewResult: null,
      isPreviewLoading: false,
      previewError: null,
    })
    mockGetAlerts.mockReset()
    mockGetHistory.mockReset()
  })

  it('enriches alerts with notification history trigger stats', async () => {
    mockGetAlerts.mockResolvedValue({
      results: [
        {
          id: 'alert-1',
          name: 'Test Alert',
          nl_description: 'Alert me when balance drops',
          enabled: true,
          event_type: 'ACCOUNT_EVENT',
          created_at: '2026-01-01T00:00:00Z',
          chains: ['ETH:mainnet'],
        },
      ],
    })

    mockGetHistory.mockResolvedValue({
      count: 2,
      results: [
        {
          notification_id: 'notif-1',
          alert_id: 'alert-1',
          alert_name: 'Test Alert',
          title: 'Alert triggered',
          message: 'Trigger 1',
          priority: 'normal',
          delivery_status: 'delivered',
          channels_delivered: 1,
          channels_failed: 0,
          created_at: '2026-01-02T12:00:00Z',
        },
        {
          notification_id: 'notif-2',
          alert_id: 'alert-1',
          alert_name: 'Test Alert',
          title: 'Alert triggered',
          message: 'Trigger 2',
          priority: 'normal',
          delivery_status: 'delivered',
          channels_delivered: 1,
          channels_failed: 0,
          created_at: '2026-01-03T12:00:00Z',
        },
      ],
      has_more: false,
    })

    await useSimpleAlerts.getState().loadAlerts()

    const [alert] = useSimpleAlerts.getState().alerts
    expect(alert.last_triggered).toBe('2026-01-03T12:00:00Z')
    expect(alert.trigger_count).toBe(2)
  })
})
