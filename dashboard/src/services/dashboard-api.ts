/**
 * Dashboard API Service
 *
 * API calls for dashboard statistics, activity, and chain monitoring
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS } from '../config/api'

// API Types
export interface DashboardStats {
  alerts: {
    total: number
    active: number
    inactive: number
  }
  groups: {
    created: number
    subscribed: number
    total: number
  }
  activity: {
    executions_24h: number
    executions_7d: number
    triggered_24h: number
  }
  wallets: {
    total: number
    watched: number
  }
  timestamp: string
}

export interface ActivityItem {
  id: string
  type: 'execution' | 'alert_created' | 'group_joined'
  title: string
  subtitle: string
  timestamp: string
  metadata: {
    alert_id?: string
    alert_name?: string
    group_id?: string
    group_name?: string
    triggered?: boolean
    chain?: string
    alert_count?: number
  }
}

export interface ActivityResponse {
  activities: ActivityItem[]
  total: number
  limit: number
  offset: number
}

export interface ActivityParams {
  limit?: number
  offset?: number
  type?: 'execution' | 'alert_created' | 'group_joined'
}

export interface ChainStats {
  chain: string
  alerts: {
    total: number
    active: number
    inactive: number
  }
  icon: string
}

export interface ChainStatsResponse {
  chains: ChainStats[]
  summary: {
    total_chains: number
    total_alerts: number
    total_active: number
  }
  timestamp: string
}

class DashboardApiService {
  /**
   * Get dashboard statistics
   * Returns aggregated stats for alerts, groups, activity, and wallets
   */
  async getStats(): Promise<DashboardStats> {
    try {
      const response = await httpClient.get<DashboardStats>(
        API_ENDPOINTS.DASHBOARD.STATS
      )
      return response.data
    } catch (error: any) {
      console.error('Get dashboard stats failed:', error)
      throw error
    }
  }

  /**
   * Get activity feed
   * Returns recent activity items (executions, created alerts, group joins)
   */
  async getActivity(params: ActivityParams = {}): Promise<ActivityResponse> {
    try {
      const response = await httpClient.get<ActivityResponse>(
        API_ENDPOINTS.DASHBOARD.ACTIVITY,
        params
      )
      return response.data
    } catch (error: any) {
      console.error('Get activity feed failed:', error)
      throw error
    }
  }

  /**
   * Get chain statistics
   * Returns alert statistics broken down by blockchain
   */
  async getChainStats(chains?: string[]): Promise<ChainStatsResponse> {
    try {
      const params = chains?.length ? { chains: chains.join(',') } : {}
      const response = await httpClient.get<ChainStatsResponse>(
        API_ENDPOINTS.DASHBOARD.CHAIN_STATS,
        params
      )
      return response.data
    } catch (error: any) {
      console.error('Get chain stats failed:', error)
      throw error
    }
  }
}

// Export singleton instance
export const dashboardApiService = new DashboardApiService()
