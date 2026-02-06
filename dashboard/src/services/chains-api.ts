/**
 * Chains API Service
 *
 * Read-only access to chain metadata (for mapping network -> chain_id).
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS, type PaginatedResponse } from '../config/api'

export interface ChainInfo {
  id: string
  name: string
  display_name: string
  chain_id: number | null
  native_token: string
}

export interface SubChainInfo {
  id: string
  name: string
  display_name: string
  network_id: number | null
  is_testnet: boolean
}

class ChainsApiService {
  async list(): Promise<PaginatedResponse<ChainInfo>> {
    try {
      const response = await httpClient.get<PaginatedResponse<ChainInfo>>(API_ENDPOINTS.CHAINS.LIST)
      return response.data
    } catch (error: unknown) {
      console.error('List chains failed:', error)
      throw error
    }
  }

  async listSubChains(chainId: string): Promise<SubChainInfo[]> {
    try {
      const response = await httpClient.get<SubChainInfo[]>(API_ENDPOINTS.CHAINS.SUB_CHAINS(chainId))
      return response.data
    } catch (error: unknown) {
      console.error('List sub-chains failed:', error)
      throw error
    }
  }
}

export const chainsApiService = new ChainsApiService()
export default chainsApiService

