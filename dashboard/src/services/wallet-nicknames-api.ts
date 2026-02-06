/**
 * Wallet Nicknames API Service
 *
 * CRUD for user-scoped wallet nicknames.
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS, type PaginatedResponse } from '../config/api'

export interface WalletNickname {
  id: string
  wallet_address: string
  chain_id: number
  custom_name: string
  notes: string
  created_at: string
  updated_at: string
}

export interface CreateWalletNicknameRequest {
  wallet_address: string
  chain_id: number
  custom_name: string
  notes?: string
}

export interface UpdateWalletNicknameRequest {
  wallet_address?: string
  chain_id?: number
  custom_name?: string
  notes?: string
}

class WalletNicknamesApiService {
  async list(): Promise<PaginatedResponse<WalletNickname>> {
    try {
      const response = await httpClient.get<PaginatedResponse<WalletNickname>>(
        API_ENDPOINTS.WALLET_NICKNAMES.LIST
      )
      return response.data
    } catch (error: unknown) {
      console.error('List wallet nicknames failed:', error)
      throw error
    }
  }

  async create(data: CreateWalletNicknameRequest): Promise<WalletNickname> {
    try {
      const response = await httpClient.post<WalletNickname>(
        API_ENDPOINTS.WALLET_NICKNAMES.CREATE,
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Create wallet nickname failed:', error)
      throw error
    }
  }

  async update(id: string, data: UpdateWalletNicknameRequest): Promise<WalletNickname> {
    try {
      const response = await httpClient.patch<WalletNickname>(
        API_ENDPOINTS.WALLET_NICKNAMES.UPDATE(id),
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Update wallet nickname failed:', error)
      throw error
    }
  }

  async delete(id: string): Promise<void> {
    try {
      await httpClient.delete<void>(API_ENDPOINTS.WALLET_NICKNAMES.DELETE(id))
    } catch (error: unknown) {
      console.error('Delete wallet nickname failed:', error)
      throw error
    }
  }
}

export const walletNicknamesApiService = new WalletNicknamesApiService()
export default walletNicknamesApiService

