/**
 * Notifications API Service
 *
 * API calls for notification channel management (Slack, Email, Telegram, Webhooks, SMS)
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS, type PaginatedResponse } from '../config/api'

// Notification Channel Types
export interface NotificationChannelEndpoint {
  id: string
  owner_type: 'user' | 'team'
  owner_id: string
  channel_type: 'email' | 'slack' | 'telegram' | 'webhook' | 'sms'
  label: string
  config: Record<string, any>
  enabled: boolean
  verified: boolean
  created_at: string
  updated_at: string
  last_used_at?: string
}

// Slack-specific config structure
export interface SlackChannelConfig {
  webhook_url: string
  channel?: string
  workspace_name?: string
}

// Telegram-specific config structure
export interface TelegramChannelConfig {
  bot_token: string
  chat_id: string
  username?: string
}

// Webhook-specific config structure
export interface WebhookChannelConfig {
  url: string
  method?: 'POST' | 'GET'
  headers?: Record<string, string>
  secret?: string
}

// SMS-specific config structure
export interface SMSChannelConfig {
  phone_number: string
  provider?: string
}

// Create channel requests
export interface CreateSlackChannelRequest {
  label: string
  webhook_url: string
  channel?: string
  workspace_name?: string
  enabled?: boolean
}

export interface CreateTelegramChannelRequest {
  label: string
  bot_token: string
  chat_id: string
  username?: string
  enabled?: boolean
}

export interface CreateWebhookChannelRequest {
  label: string
  url: string
  method?: 'POST' | 'GET'
  headers?: Record<string, string>
  secret?: string
  events?: string[]
  enabled?: boolean
}

export interface CreateSMSChannelRequest {
  label: string
  phone_number: string
  provider?: string
  enabled?: boolean
}

// Update channel request
export interface UpdateChannelRequest {
  label?: string
  config?: Record<string, any>
  enabled?: boolean
}

// List channels params
export interface ChannelsListParams {
  page?: number
  page_size?: number
  channel_type?: 'email' | 'slack' | 'telegram' | 'webhook' | 'sms'
  enabled?: boolean
  owner_type?: 'user' | 'team'
}

// Test message request
export interface TestMessageRequest {
  message?: string
}

// Delivery stats response
export interface DeliveryStatsResponse {
  channel_id: string
  success_count: number
  failure_count: number
  last_success_at?: string
  last_failure_at?: string
  last_error?: string
}

// Webhook health metrics response
export interface WebhookHealthMetrics {
  endpoint_url: string
  success_count: number
  failure_count: number
  avg_response_time_ms: number
  last_success_at?: number
  last_failure_at?: number
  last_error?: string
  consecutive_failures: number
  is_healthy: boolean
}

export interface NotificationHistoryItem {
  notification_id: string
  alert_id: string
  alert_name: string
  title: string
  message: string
  priority: string
  delivery_status: string
  channels_delivered: number
  channels_failed: number
  created_at: string
  transaction_hash?: string | null
  chain_id?: string | null
  block_number?: number | null
  value_usd?: number | null
  target_channels?: string[] | null
}

export interface NotificationHistoryResponse {
  count: number
  results: NotificationHistoryItem[]
  has_more: boolean
}

export interface NotificationHistoryParams {
  limit?: number
  offset?: number
  priority?: string
  alert_id?: string
  start_date?: string
  end_date?: string
}

class NotificationsApiService {
  // Get notification channels list
  async getChannels(params: ChannelsListParams = {}): Promise<PaginatedResponse<NotificationChannelEndpoint>> {
    try {
      const response = await httpClient.get<PaginatedResponse<NotificationChannelEndpoint>>(
        API_ENDPOINTS.NOTIFICATIONS.CHANNELS,
        params
      )
      return response.data
    } catch (error: any) {
      console.error('Get notification channels failed:', error)
      throw error
    }
  }

  // Get single channel
  async getChannel(channelId: string): Promise<NotificationChannelEndpoint> {
    try {
      const response = await httpClient.get<NotificationChannelEndpoint>(
        `${API_ENDPOINTS.NOTIFICATIONS.CHANNELS}${channelId}/`
      )
      return response.data
    } catch (error: any) {
      console.error('Get notification channel failed:', error)
      throw error
    }
  }

  // Create Slack channel
  async createSlackChannel(data: CreateSlackChannelRequest): Promise<NotificationChannelEndpoint> {
    try {
      const payload = {
        channel_type: 'slack',
        label: data.label,
        config: {
          webhook_url: data.webhook_url,
          channel: data.channel || '#alerts',
          workspace_name: data.workspace_name || 'Ekko Workspace'
        },
        enabled: data.enabled !== undefined ? data.enabled : true,
        verified: false
      }

      const response = await httpClient.post<NotificationChannelEndpoint>(
        API_ENDPOINTS.NOTIFICATIONS.CHANNELS,
        payload
      )
      return response.data
    } catch (error: any) {
      console.error('Create Slack channel failed:', error)
      throw error
    }
  }

  // Create Telegram channel
  async createTelegramChannel(data: CreateTelegramChannelRequest): Promise<NotificationChannelEndpoint> {
    try {
      const payload = {
        channel_type: 'telegram',
        label: data.label,
        config: {
          bot_token: data.bot_token,
          chat_id: data.chat_id,
          username: data.username
        },
        enabled: data.enabled !== undefined ? data.enabled : true,
        verified: false
      }

      const response = await httpClient.post<NotificationChannelEndpoint>(
        API_ENDPOINTS.NOTIFICATIONS.CHANNELS,
        payload
      )
      return response.data
    } catch (error: any) {
      console.error('Create Telegram channel failed:', error)
      throw error
    }
  }

  // Create Webhook channel
  async createWebhookChannel(data: CreateWebhookChannelRequest): Promise<NotificationChannelEndpoint> {
    try {
      const payload = {
        channel_type: 'webhook',
        label: data.label,
        config: {
          url: data.url,
          method: data.method || 'POST',
          headers: data.headers || {},
          secret: data.secret,
          events: data.events
        },
        enabled: data.enabled !== undefined ? data.enabled : true,
        verified: false
      }

      const response = await httpClient.post<NotificationChannelEndpoint>(
        API_ENDPOINTS.NOTIFICATIONS.CHANNELS,
        payload
      )
      return response.data
    } catch (error: any) {
      console.error('Create Webhook channel failed:', error)
      throw error
    }
  }

  // Create SMS channel
  async createSMSChannel(data: CreateSMSChannelRequest): Promise<NotificationChannelEndpoint> {
    try {
      const payload = {
        channel_type: 'sms',
        label: data.label,
        config: {
          phone_number: data.phone_number,
          provider: data.provider
        },
        enabled: data.enabled !== undefined ? data.enabled : true,
        verified: false
      }

      const response = await httpClient.post<NotificationChannelEndpoint>(
        API_ENDPOINTS.NOTIFICATIONS.CHANNELS,
        payload
      )
      return response.data
    } catch (error: any) {
      console.error('Create SMS channel failed:', error)
      throw error
    }
  }

  // Update channel
  async updateChannel(channelId: string, data: UpdateChannelRequest): Promise<NotificationChannelEndpoint> {
    try {
      const response = await httpClient.patch<NotificationChannelEndpoint>(
        `${API_ENDPOINTS.NOTIFICATIONS.CHANNELS}${channelId}/`,
        data
      )
      return response.data
    } catch (error: any) {
      console.error('Update notification channel failed:', error)
      throw error
    }
  }

  // Delete channel
  async deleteChannel(channelId: string): Promise<void> {
    try {
      await httpClient.delete(`${API_ENDPOINTS.NOTIFICATIONS.CHANNELS}${channelId}/`)
    } catch (error: any) {
      console.error('Delete notification channel failed:', error)
      throw error
    }
  }

  // Toggle channel enabled/disabled
  async toggleChannel(channelId: string, enabled: boolean): Promise<NotificationChannelEndpoint> {
    try {
      const response = await httpClient.patch<NotificationChannelEndpoint>(
        `${API_ENDPOINTS.NOTIFICATIONS.CHANNELS}${channelId}/`,
        { enabled }
      )
      return response.data
    } catch (error: any) {
      console.error('Toggle notification channel failed:', error)
      throw error
    }
  }

  // Send test message to channel
  async testChannel(channelId: string, message?: string): Promise<{ success: boolean; message: string }> {
    try {
      const payload: TestMessageRequest = {}
      if (message) {
        payload.message = message
      }

      const response = await httpClient.post<{ success: boolean; message: string }>(
        `${API_ENDPOINTS.NOTIFICATIONS.CHANNELS}${channelId}/test/`,
        payload
      )
      return response.data
    } catch (error: any) {
      console.error('Test notification channel failed:', error)
      throw error
    }
  }

  // Get delivery statistics for a channel
  async getChannelStats(channelId: string): Promise<DeliveryStatsResponse> {
    try {
      const response = await httpClient.get<DeliveryStatsResponse>(
        `${API_ENDPOINTS.NOTIFICATIONS.CHANNELS}${channelId}/stats/`
      )
      return response.data
    } catch (error: any) {
      console.error('Get channel stats failed:', error)
      throw error
    }
  }

  // Verify channel (for channels that require verification like Telegram)
  async verifyChannel(channelId: string, verificationCode?: string): Promise<NotificationChannelEndpoint> {
    try {
      const response = await httpClient.post<NotificationChannelEndpoint>(
        `${API_ENDPOINTS.NOTIFICATIONS.CHANNELS}${channelId}/verify/`,
        { code: verificationCode }
      )
      return response.data
    } catch (error: any) {
      console.error('Verify notification channel failed:', error)
      throw error
    }
  }

  // Get webhook health metrics (for webhook channels only)
  async getWebhookHealth(channelId: string): Promise<WebhookHealthMetrics> {
    try {
      const response = await httpClient.get<WebhookHealthMetrics>(
        `${API_ENDPOINTS.NOTIFICATIONS.CHANNELS}${channelId}/health/`
      )
      return response.data
    } catch (error: any) {
      console.error('Get webhook health failed:', error)
      throw error
    }
  }

  async getHistory(
    params: NotificationHistoryParams = {}
  ): Promise<NotificationHistoryResponse> {
    try {
      const response = await httpClient.get<NotificationHistoryResponse>(
        API_ENDPOINTS.NOTIFICATIONS.HISTORY,
        params
      )
      return response.data
    } catch (error: any) {
      console.error('Get notification history failed:', error)
      throw error
    }
  }
}

export const notificationsApiService = new NotificationsApiService()
export default notificationsApiService
