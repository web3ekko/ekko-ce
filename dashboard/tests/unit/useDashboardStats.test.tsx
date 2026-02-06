import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'

import type { DashboardStats } from '../../src/services/dashboard-api'

const callbacks = new Map<string, (data?: unknown) => void>()

vi.mock('../../src/services/dashboard-api', () => ({
  dashboardApiService: {
    getStats: vi.fn(),
  },
}))

vi.mock('../../src/services/websocket', () => ({
  EVENTS: {
    ALERT_TRIGGERED: 'alert:triggered',
    ALERT_CREATED: 'alert:created',
    ALERT_UPDATED: 'alert:updated',
    ALERT_DELETED: 'alert:deleted',
    ALERT_STATUS_CHANGED: 'alert:status',
    WALLET_ADDED: 'wallet:added',
    WALLET_REMOVED: 'wallet:removed',
  },
  websocketService: {
    on: vi.fn((event: string, callback: (data?: unknown) => void) => {
      callbacks.set(event, callback)
      return () => callbacks.delete(event)
    }),
  },
}))

const sampleStats: DashboardStats = {
  alerts: { total: 4, active: 3, inactive: 1 },
  groups: { created: 2, subscribed: 1, total: 2 },
  activity: { executions_24h: 7, executions_7d: 22, triggered_24h: 3 },
  wallets: { total: 5, watched: 5 },
  timestamp: '2026-01-30T12:00:00Z',
}

describe('useDashboardStats', () => {
  beforeEach(() => {
    callbacks.clear()
    vi.resetModules()
  })

  it('loads stats on mount', async () => {
    const { dashboardApiService } = await import('../../src/services/dashboard-api')
    vi.mocked(dashboardApiService.getStats).mockResolvedValue(sampleStats)

    const { useDashboardStats } = await import('../../src/hooks/useDashboardStats')

    const { result, unmount } = renderHook(() =>
      useDashboardStats({ refreshIntervalMs: 0, refreshOnEvents: false })
    )

    await waitFor(() => {
      expect(result.current.stats).toEqual(sampleStats)
    })

    expect(dashboardApiService.getStats).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('refreshes when an alert-triggered event arrives', async () => {
    const { dashboardApiService } = await import('../../src/services/dashboard-api')
    vi.mocked(dashboardApiService.getStats).mockResolvedValue(sampleStats)

    const { useDashboardStats } = await import('../../src/hooks/useDashboardStats')

    const { unmount } = renderHook(() => useDashboardStats({ refreshIntervalMs: 0 }))

    await waitFor(() => {
      expect(dashboardApiService.getStats).toHaveBeenCalledTimes(1)
    })

    act(() => {
      callbacks.get('alert:triggered')?.({})
    })

    await waitFor(() => {
      expect(dashboardApiService.getStats).toHaveBeenCalledTimes(2)
    })
    unmount()
  })
})
