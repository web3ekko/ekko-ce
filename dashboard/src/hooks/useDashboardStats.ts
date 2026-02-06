/**
 * useDashboardStats
 *
 * Shared dashboard stats hook with periodic refresh and WebSocket-driven updates.
 */

import { useCallback, useEffect } from 'react'
import { useDashboardStatsStore } from '../store/dashboard-stats'
import { websocketService, EVENTS } from '../services/websocket'

const DEFAULT_REFRESH_INTERVAL_MS = 60000
const EVENT_REFRESH_COOLDOWN_MS = 5000

let sharedSubscriberCount = 0
let sharedIntervalId: ReturnType<typeof setInterval> | null = null
let sharedIntervalMs: number | null = null
let sharedEventUnsubscribers: Array<() => void> = []
let lastEventRefreshAt = 0

interface UseDashboardStatsOptions {
  refreshIntervalMs?: number
  refreshOnEvents?: boolean
}

export function useDashboardStats(options: UseDashboardStatsOptions = {}) {
  const { refreshIntervalMs = DEFAULT_REFRESH_INTERVAL_MS, refreshOnEvents = true } = options

  const stats = useDashboardStatsStore((state) => state.stats)
  const isLoading = useDashboardStatsStore((state) => state.isLoading)
  const error = useDashboardStatsStore((state) => state.error)
  const lastUpdatedAt = useDashboardStatsStore((state) => state.lastUpdatedAt)
  const loadStats = useDashboardStatsStore((state) => state.loadStats)

  const refresh = useCallback(
    (silent = true) => loadStats({ silent }),
    [loadStats]
  )

  useEffect(() => {
    refresh(false)
  }, [refresh])

  useEffect(() => {
    sharedSubscriberCount += 1

    const sharedRefresh = () => {
      useDashboardStatsStore.getState().loadStats({ silent: true })
    }

    if (refreshOnEvents && sharedEventUnsubscribers.length === 0) {
      const handler = () => {
        const now = Date.now()
        if (now - lastEventRefreshAt < EVENT_REFRESH_COOLDOWN_MS) {
          return
        }
        lastEventRefreshAt = now
        sharedRefresh()
      }

      sharedEventUnsubscribers = [
        websocketService.on(EVENTS.ALERT_TRIGGERED, handler),
        websocketService.on(EVENTS.ALERT_CREATED, handler),
        websocketService.on(EVENTS.ALERT_UPDATED, handler),
        websocketService.on(EVENTS.ALERT_DELETED, handler),
        websocketService.on(EVENTS.ALERT_STATUS_CHANGED, handler),
        websocketService.on(EVENTS.WALLET_ADDED, handler),
        websocketService.on(EVENTS.WALLET_REMOVED, handler),
        websocketService.on('dashboard:stats', handler),
      ]
    }

    if (refreshIntervalMs && refreshIntervalMs > 0) {
      if (sharedIntervalId === null || (sharedIntervalMs !== null && refreshIntervalMs < sharedIntervalMs)) {
        if (sharedIntervalId) {
          clearInterval(sharedIntervalId)
        }
        sharedIntervalMs = refreshIntervalMs
        sharedIntervalId = setInterval(() => {
          sharedRefresh()
        }, refreshIntervalMs)
      }
    }

    return () => {
      sharedSubscriberCount -= 1
      if (sharedSubscriberCount <= 0) {
        sharedSubscriberCount = 0
        if (sharedIntervalId) {
          clearInterval(sharedIntervalId)
          sharedIntervalId = null
        }
        sharedIntervalMs = null
        sharedEventUnsubscribers.forEach((unsubscribe) => unsubscribe())
        sharedEventUnsubscribers = []
        lastEventRefreshAt = 0
      }
    }
  }, [refreshIntervalMs, refreshOnEvents])

  return {
    stats,
    isLoading,
    error,
    lastUpdatedAt,
    refresh: () => refresh(false),
  }
}
