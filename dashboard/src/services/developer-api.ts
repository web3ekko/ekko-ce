/**
 * Developer API Service
 *
 * API calls for API keys, usage, and endpoint catalog.
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS } from '../config/api'

export interface ApiKeyRateLimit {
  requests_per_minute: number
  requests_per_day: number
}

export interface ApiKeyRecord {
  id: string
  name: string
  key_prefix: string
  access_level: 'full' | 'read_only' | 'limited'
  status: 'active' | 'expires_soon' | 'expired' | 'revoked'
  expires_at?: string | null
  last_used_at?: string | null
  usage_count: number
  rate_limit: ApiKeyRateLimit
  created_at: string
}

export interface ApiKeyCreateResponse {
  key: string
  key_details: ApiKeyRecord
}

export interface ApiUsageRecord {
  date: string
  requests: number
  errors: number
}

export interface ApiUsageResponse {
  usage: ApiUsageRecord[]
  totals: {
    requests: number
    errors: number
  }
}

export interface ApiEndpointParameter {
  name: string
  type: string
  required: boolean
  description?: string
}

export interface ApiEndpointRecord {
  id: string
  path: string
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  description: string
  parameters: ApiEndpointParameter[]
  example_request?: Record<string, unknown> | null
  example_response?: Record<string, unknown> | null
}

class DeveloperApiService {
  async getApiKeys(): Promise<ApiKeyRecord[]> {
    const response = await httpClient.get<{ keys: ApiKeyRecord[] }>(
      API_ENDPOINTS.DEVELOPER.API_KEYS
    )
    return response.data.keys
  }

  async createApiKey(payload: {
    name: string
    access_level: ApiKeyRecord['access_level']
    expires_at?: string | null
    rate_limit?: ApiKeyRateLimit
  }): Promise<ApiKeyCreateResponse> {
    const response = await httpClient.post<ApiKeyCreateResponse>(
      API_ENDPOINTS.DEVELOPER.API_KEYS,
      payload
    )
    return response.data
  }

  async updateApiKey(
    apiKeyId: string,
    payload: Partial<Pick<ApiKeyRecord, 'name' | 'access_level' | 'expires_at'>> & {
      rate_limit?: ApiKeyRateLimit
    }
  ): Promise<ApiKeyRecord> {
    const response = await httpClient.patch<ApiKeyRecord>(
      API_ENDPOINTS.DEVELOPER.API_KEY_DETAIL(apiKeyId),
      payload
    )
    return response.data
  }

  async deleteApiKey(apiKeyId: string): Promise<void> {
    await httpClient.delete(API_ENDPOINTS.DEVELOPER.API_KEY_DETAIL(apiKeyId))
  }

  async revokeApiKey(apiKeyId: string): Promise<ApiKeyRecord> {
    const response = await httpClient.post<ApiKeyRecord>(
      API_ENDPOINTS.DEVELOPER.API_KEY_REVOKE(apiKeyId),
      {}
    )
    return response.data
  }

  async getUsage(days: number = 7): Promise<ApiUsageResponse> {
    const response = await httpClient.get<ApiUsageResponse>(
      API_ENDPOINTS.DEVELOPER.USAGE,
      { days }
    )
    return response.data
  }

  async getEndpoints(): Promise<ApiEndpointRecord[]> {
    const response = await httpClient.get<{ endpoints: ApiEndpointRecord[] }>(
      API_ENDPOINTS.DEVELOPER.ENDPOINTS
    )
    return response.data.endpoints
  }
}

export const developerApiService = new DeveloperApiService()
export default developerApiService
