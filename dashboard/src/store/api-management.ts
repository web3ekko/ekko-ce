/**
 * API Management Store
 *
 * State management for developer API keys, usage, and webhooks
 */

import { create } from 'zustand'
import developerApiService, { type ApiEndpointRecord, type ApiKeyRecord, type ApiUsageRecord } from '../services/developer-api'
import notificationsApiService, { type NotificationChannelEndpoint } from '../services/notifications-api'

export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  access_level: 'full' | 'read_only' | 'limited'
  created_at: string
  expires_at?: string | null
  status: 'active' | 'expires_soon' | 'expired' | 'revoked'
  last_used_at?: string | null
  usage_count: number
  rate_limit: {
    requests_per_minute: number
    requests_per_day: number
  }
}

export interface ApiUsage {
  date: string
  requests: number
  errors: number
  success_rate: number
}

export interface WebhookConfig {
  id: string
  name: string
  url: string
  events: string[]
  status: 'connected' | 'disconnected' | 'error'
  secret?: string
  created_at: string
  last_delivery?: string | null
  delivery_count: number
}

export interface ApiEndpoint {
  id: string
  path: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  description: string
  parameters?: Array<{
    name: string
    type: string
    required: boolean
    description: string
  }>
  example_request?: any
  example_response?: any
}

interface ApiManagementState {
  // State
  apiKeys: ApiKey[]
  webhooks: WebhookConfig[]
  usage: ApiUsage[]
  endpoints: ApiEndpoint[]
  isLoading: boolean
  error: string | null

  // API Tester State
  selectedEndpoint: string | null
  testRequest: {
    method: string
    url: string
    headers: Record<string, string>
    body: string
  }
  testResponse: {
    status?: number
    headers?: Record<string, string>
    body?: any
    error?: string
  } | null

  // Actions
  loadApiKeys: () => Promise<void>
  loadWebhooks: () => Promise<void>
  loadUsage: () => Promise<void>
  loadEndpoints: () => Promise<void>
  createApiKey: (data: { name: string; access_level: ApiKey['access_level']; expires_at?: string | null; rate_limit?: ApiKey['rate_limit'] }) => Promise<string>
  updateApiKey: (id: string, updates: Partial<ApiKey>) => Promise<void>
  deleteApiKey: (id: string) => Promise<void>
  revokeApiKey: (id: string) => Promise<void>
  createWebhook: (data: Omit<WebhookConfig, 'id' | 'created_at' | 'delivery_count' | 'last_delivery' | 'status'>) => Promise<void>
  updateWebhook: (id: string, updates: Partial<WebhookConfig>) => Promise<void>
  deleteWebhook: (id: string) => Promise<void>
  testWebhook: (id: string) => Promise<void>
  setSelectedEndpoint: (endpoint: string | null) => void
  updateTestRequest: (updates: Partial<ApiManagementState['testRequest']>) => void
  executeApiTest: () => Promise<void>
  clearTestResponse: () => void
  setError: (error: string | null) => void
}

const mapApiKey = (record: ApiKeyRecord): ApiKey => ({
  id: record.id,
  name: record.name,
  key_prefix: record.key_prefix,
  access_level: record.access_level,
  created_at: record.created_at,
  expires_at: record.expires_at || null,
  status: record.status,
  last_used_at: record.last_used_at || null,
  usage_count: record.usage_count,
  rate_limit: record.rate_limit,
})

const mapUsage = (record: ApiUsageRecord): ApiUsage => {
  const successRate = record.requests > 0 ? (record.requests - record.errors) / record.requests : 0
  return {
    date: record.date,
    requests: record.requests,
    errors: record.errors,
    success_rate: Number((successRate * 100).toFixed(1)),
  }
}

const mapEndpoint = (record: ApiEndpointRecord): ApiEndpoint => ({
  id: record.id,
  path: record.path,
  method: record.method,
  description: record.description,
  parameters: record.parameters,
  example_request: record.example_request,
  example_response: record.example_response,
})

const mapWebhook = (endpoint: NotificationChannelEndpoint, deliveryCount: number): WebhookConfig => {
  const config = endpoint.config || {}
  const events = Array.isArray(config.events) ? config.events : []
  const status = endpoint.enabled ? 'connected' : 'disconnected'

  return {
    id: endpoint.id,
    name: endpoint.label,
    url: config.url || config.webhook_url || '',
    events,
    status,
    secret: config.secret,
    created_at: endpoint.created_at,
    last_delivery: endpoint.last_used_at || null,
    delivery_count: deliveryCount,
  }
}

export const useApiManagementStore = create<ApiManagementState>((set, get) => ({
  // Initial state
  apiKeys: [],
  webhooks: [],
  usage: [],
  endpoints: [],
  isLoading: false,
  error: null,
  selectedEndpoint: null,
  testRequest: {
    method: 'GET',
    url: '',
    headers: { Authorization: 'Bearer your-api-key' },
    body: '',
  },
  testResponse: null,

  // Load API keys
  loadApiKeys: async () => {
    set({ isLoading: true, error: null })
    try {
      const keys = await developerApiService.getApiKeys()
      set({ apiKeys: keys.map(mapApiKey), isLoading: false })
    } catch (error) {
      console.error('Failed to load API keys:', error)
      set({ error: 'Failed to load API keys', isLoading: false })
    }
  },

  // Load webhooks
  loadWebhooks: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await notificationsApiService.getChannels({ channel_type: 'webhook' })
      const endpoints = response.results || []
      const stats = await Promise.all(
        endpoints.map(async (endpoint) => {
          try {
            const result = await notificationsApiService.getChannelStats(endpoint.id)
            return result.success_count + result.failure_count
          } catch (error) {
            console.warn('Failed to load webhook stats:', error)
            return 0
          }
        })
      )
      const mapped = endpoints.map((endpoint, index) => mapWebhook(endpoint, stats[index] || 0))
      set({ webhooks: mapped, isLoading: false })
    } catch (error) {
      console.error('Failed to load webhooks:', error)
      set({ error: 'Failed to load webhooks', isLoading: false })
    }
  },

  // Load usage data
  loadUsage: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await developerApiService.getUsage(7)
      set({ usage: response.usage.map(mapUsage), isLoading: false })
    } catch (error) {
      console.error('Failed to load usage data:', error)
      set({ error: 'Failed to load usage data', isLoading: false })
    }
  },

  // Load endpoints
  loadEndpoints: async () => {
    set({ isLoading: true, error: null })
    try {
      const endpoints = await developerApiService.getEndpoints()
      set({ endpoints: endpoints.map(mapEndpoint), isLoading: false })
    } catch (error) {
      console.error('Failed to load endpoints:', error)
      set({ error: 'Failed to load endpoints', isLoading: false })
    }
  },

  // Create API key
  createApiKey: async (keyData) => {
    const response = await developerApiService.createApiKey(keyData)
    set((state) => ({
      apiKeys: [mapApiKey(response.key_details), ...state.apiKeys],
    }))
    return response.key
  },

  // Update API key
  updateApiKey: async (id, updates) => {
    await developerApiService.updateApiKey(id, updates)
    const keys = await developerApiService.getApiKeys()
    set({ apiKeys: keys.map(mapApiKey) })
  },

  // Delete API key
  deleteApiKey: async (id) => {
    await developerApiService.deleteApiKey(id)
    set((state) => ({
      apiKeys: state.apiKeys.filter((key) => key.id !== id),
    }))
  },

  // Revoke API key
  revokeApiKey: async (id) => {
    const updated = await developerApiService.revokeApiKey(id)
    set((state) => ({
      apiKeys: state.apiKeys.map((key) => (key.id === id ? mapApiKey(updated) : key)),
    }))
  },

  // Create webhook
  createWebhook: async (webhookData) => {
    const response = await notificationsApiService.createWebhookChannel({
      label: webhookData.name,
      url: webhookData.url,
      secret: webhookData.secret,
      events: webhookData.events,
    })
    const mapped = mapWebhook(response, 0)
    set((state) => ({
      webhooks: [mapped, ...state.webhooks],
    }))
  },

  // Update webhook
  updateWebhook: async (id, updates) => {
    const configUpdates: Record<string, unknown> = {}
    if (updates.url) {
      configUpdates.url = updates.url
    }
    if (updates.secret) {
      configUpdates.secret = updates.secret
    }
    if (updates.events) {
      configUpdates.events = updates.events
    }
    const response = await notificationsApiService.updateChannel(id, {
      label: updates.name,
      enabled: updates.status ? updates.status === 'connected' : undefined,
      config: Object.keys(configUpdates).length ? configUpdates : undefined,
    })
    const stats = await notificationsApiService.getChannelStats(id).catch(() => ({ success_count: 0, failure_count: 0 }))
    const deliveryCount = stats.success_count + stats.failure_count
    set((state) => ({
      webhooks: state.webhooks.map((webhook) => (webhook.id === id ? mapWebhook(response, deliveryCount) : webhook)),
    }))
  },

  // Delete webhook
  deleteWebhook: async (id) => {
    await notificationsApiService.deleteChannel(id)
    set((state) => ({
      webhooks: state.webhooks.filter((webhook) => webhook.id !== id),
    }))
  },

  // Test webhook
  testWebhook: async (id) => {
    await notificationsApiService.testChannel(id)
    const stats = await notificationsApiService.getChannelStats(id).catch(() => ({ success_count: 0, failure_count: 0 }))
    const deliveryCount = stats.success_count + stats.failure_count
    set((state) => ({
      webhooks: state.webhooks.map((webhook) =>
        webhook.id === id
          ? { ...webhook, last_delivery: new Date().toISOString(), delivery_count: deliveryCount }
          : webhook
      ),
    }))
  },

  // Set selected endpoint
  setSelectedEndpoint: (endpoint) => {
    const state = get()
    const endpointData = state.endpoints.find((e) => `${e.method} ${e.path}` === endpoint)

    if (endpointData) {
      set({
        selectedEndpoint: endpoint,
        testRequest: {
          ...state.testRequest,
          method: endpointData.method,
          url: `${window.location.origin}${endpointData.path}`,
          body: endpointData.example_request ? JSON.stringify(endpointData.example_request, null, 2) : '',
        },
      })
    } else {
      set({ selectedEndpoint: endpoint })
    }
  },

  // Update test request
  updateTestRequest: (updates) => {
    set((state) => ({
      testRequest: { ...state.testRequest, ...updates },
    }))
  },

  // Execute API test
  executeApiTest: async () => {
    const { testRequest } = get()
    set({ isLoading: true, testResponse: null })

    try {
      const response = await fetch(testRequest.url, {
        method: testRequest.method,
        headers: testRequest.headers,
        body: ['GET', 'HEAD'].includes(testRequest.method.toUpperCase())
          ? undefined
          : testRequest.body || undefined,
      })

      let body
      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        body = await response.json()
      } else {
        body = await response.text()
      }

      set({
        testResponse: {
          status: response.status,
          headers: Object.fromEntries(response.headers.entries()),
          body,
        },
        isLoading: false,
      })
    } catch (error) {
      set({
        testResponse: { error: (error as Error).message || 'Request failed' },
        isLoading: false,
      })
    }
  },

  // Clear test response
  clearTestResponse: () => {
    set({ testResponse: null })
  },

  // Set error
  setError: (error) => {
    set({ error })
  },
}))
