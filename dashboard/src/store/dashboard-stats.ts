/**
 * Dashboard Stats Store
 *
 * Shared stats state for dashboard widgets with refresh deduplication.
 */

import { create } from 'zustand'
import { dashboardApiService, type DashboardStats } from '../services/dashboard-api'

interface DashboardStatsState {
  stats: DashboardStats | null
  isLoading: boolean
  error: string | null
  lastUpdatedAt: string | null
  loadStats: (options?: { silent?: boolean }) => Promise<void>
}

let inFlight: Promise<void> | null = null

export const useDashboardStatsStore = create<DashboardStatsState>((set, get) => ({
  stats: null,
  isLoading: false,
  error: null,
  lastUpdatedAt: null,

  loadStats: async (options = {}) => {
    if (inFlight) {
      return inFlight
    }

    const { silent = false } = options
    const hasStats = get().stats !== null
    const shouldShowLoading = !silent || !hasStats

    if (shouldShowLoading) {
      set({ isLoading: true, error: null })
    } else {
      set({ error: null })
    }

    inFlight = (async () => {
      try {
        const response = await dashboardApiService.getStats()
        set({
          stats: response,
          isLoading: false,
          error: null,
          lastUpdatedAt: response.timestamp || new Date().toISOString(),
        })
      } catch (error: any) {
        console.error('Failed to load dashboard stats:', error)
        set({
          isLoading: false,
          error: error?.message || 'Failed to load dashboard stats',
        })
      } finally {
        inFlight = null
      }
    })()

    return inFlight
  },
}))
