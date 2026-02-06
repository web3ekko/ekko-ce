/**
 * Newsfeed API Service
 *
 * API calls for transaction newsfeed - displays blockchain transactions
 * for user's monitored wallets from DuckLake analytics
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS } from '../config/api'
import type {
  NewsfeedTransaction,
  NewsfeedResponse,
  NewsfeedParams,
  NewsfeedTransactionType,
} from '../types/newsfeed'

// Default parameters for newsfeed requests
const DEFAULT_PARAMS: Required<Omit<NewsfeedParams, 'chains' | 'start_date' | 'transaction_type'>> = {
  limit: 50,
  offset: 0,
}

// Maximum allowed limit per request
const MAX_LIMIT = 500

class NewsfeedApiService {
  /**
   * Get transaction newsfeed for user's monitored wallets
   *
   * Fetches transactions from DuckLake for all wallet addresses
   * the user is monitoring via their alerts
   *
   * @param params - Query parameters for filtering and pagination
   * @returns Promise<NewsfeedResponse>
   */
  async getTransactions(params: NewsfeedParams = {}): Promise<NewsfeedResponse> {
    try {
      // Validate and normalize parameters
      const normalizedParams = this.normalizeParams(params)

      const response = await httpClient.get<NewsfeedResponse>(
        API_ENDPOINTS.ANALYTICS.NEWSFEED_TRANSACTIONS,
        normalizedParams
      )
      return response.data
    } catch (error: any) {
      console.error('Get newsfeed transactions failed:', error)
      throw error
    }
  }

  /**
   * Get transactions with auto-pagination
   *
   * Fetches multiple pages of transactions up to a total limit
   *
   * @param totalLimit - Maximum total transactions to fetch
   * @param params - Query parameters for filtering
   * @returns Promise<NewsfeedTransaction[]>
   */
  async getAllTransactions(
    totalLimit: number,
    params: Omit<NewsfeedParams, 'limit' | 'offset'> = {}
  ): Promise<NewsfeedTransaction[]> {
    const allTransactions: NewsfeedTransaction[] = []
    let offset = 0
    const pageSize = Math.min(totalLimit, MAX_LIMIT)

    while (allTransactions.length < totalLimit) {
      const response = await this.getTransactions({
        ...params,
        limit: pageSize,
        offset,
      })

      allTransactions.push(...response.transactions)

      // Stop if we got fewer than requested (no more data)
      if (response.transactions.length < pageSize) {
        break
      }

      offset += pageSize

      // Safety check to prevent infinite loops
      if (offset > 10000) {
        console.warn('Newsfeed: Reached maximum offset limit')
        break
      }
    }

    return allTransactions.slice(0, totalLimit)
  }

  /**
   * Get transactions filtered by chain
   *
   * @param chainIds - Array of chain IDs to filter by
   * @param params - Additional query parameters
   * @returns Promise<NewsfeedResponse>
   */
  async getTransactionsByChain(
    chainIds: string[],
    params: Omit<NewsfeedParams, 'chains'> = {}
  ): Promise<NewsfeedResponse> {
    return this.getTransactions({
      ...params,
      chains: chainIds.join(','),
    })
  }

  /**
   * Get transactions filtered by type
   *
   * @param transactionType - Transaction type to filter by
   * @param params - Additional query parameters
   * @returns Promise<NewsfeedResponse>
   */
  async getTransactionsByType(
    transactionType: NewsfeedTransactionType,
    params: Omit<NewsfeedParams, 'transaction_type'> = {}
  ): Promise<NewsfeedResponse> {
    return this.getTransactions({
      ...params,
      transaction_type: transactionType,
    })
  }

  /**
   * Get transactions from the last N hours
   *
   * @param hours - Number of hours to look back
   * @param params - Additional query parameters
   * @returns Promise<NewsfeedResponse>
   */
  async getRecentTransactions(
    hours: number = 24,
    params: Omit<NewsfeedParams, 'start_date'> = {}
  ): Promise<NewsfeedResponse> {
    const startDate = new Date()
    startDate.setHours(startDate.getHours() - hours)

    return this.getTransactions({
      ...params,
      start_date: startDate.toISOString(),
    })
  }

  /**
   * Normalize and validate request parameters
   */
  private normalizeParams(params: NewsfeedParams): Record<string, string | number> {
    const normalized: Record<string, string | number> = {}

    // Limit with bounds checking
    const limit = params.limit ?? DEFAULT_PARAMS.limit
    normalized.limit = Math.min(Math.max(1, limit), MAX_LIMIT)

    // Offset with bounds checking
    const offset = params.offset ?? DEFAULT_PARAMS.offset
    normalized.offset = Math.max(0, offset)

    // Optional filters
    if (params.chains) {
      normalized.chains = params.chains
    }

    if (params.start_date) {
      // Validate ISO 8601 format
      const date = new Date(params.start_date)
      if (!isNaN(date.getTime())) {
        normalized.start_date = params.start_date
      }
    }

    if (params.transaction_type) {
      normalized.transaction_type = params.transaction_type
    }

    return normalized
  }
}

// Export singleton instance
export const newsfeedApiService = new NewsfeedApiService()

// Export types for convenience
export type { NewsfeedTransaction, NewsfeedResponse, NewsfeedParams }
