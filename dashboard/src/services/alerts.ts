/**
 * Alert API Service
 * 
 * API client for alert management operations
 */

import { apiClient } from './api'
import type {
  Alert,
  AlertTemplate,
  AlertExecution,
  AlertMetrics,
  CreateAlertRequest,
  UpdateAlertRequest,
  AlertListResponse,
  AlertFilters,
  AlertSortOptions,
  NotificationChannel,
  ChannelType,
  ChannelConfiguration,
} from '../types/alerts'

class AlertApiService {
  /**
   * Alert CRUD operations
   */
  
  async getAlerts(
    filters?: AlertFilters,
    sort?: AlertSortOptions,
    page = 1,
    perPage = 20
  ): Promise<AlertListResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      per_page: perPage.toString(),
    })

    if (filters) {
      if (filters.status?.length) {
        params.append('status', filters.status.join(','))
      }
      if (filters.event_type?.length) {
        params.append('event_type', filters.event_type.join(','))
      }
      if (filters.created_by?.length) {
        params.append('created_by', filters.created_by.join(','))
      }
      if (filters.team_id) {
        params.append('team_id', filters.team_id)
      }
      if (filters.search) {
        params.append('search', filters.search)
      }
      if (filters.tags?.length) {
        params.append('tags', filters.tags.join(','))
      }
      if (filters.date_range) {
        params.append('date_start', filters.date_range.start)
        params.append('date_end', filters.date_range.end)
      }
    }

    if (sort) {
      params.append('sort', `${sort.direction === 'desc' ? '-' : ''}${sort.field}`)
    }

    return apiClient.request<AlertListResponse>(`/api/alerts/?${params}`)
  }

  async getAlert(alertId: string): Promise<Alert> {
    return apiClient.request<Alert>(`/api/alerts/${alertId}/`)
  }

  async createAlert(data: CreateAlertRequest): Promise<Alert> {
    return apiClient.request<Alert>('/api/alerts/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateAlert(alertId: string, data: UpdateAlertRequest): Promise<Alert> {
    return apiClient.request<Alert>(`/api/alerts/${alertId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async deleteAlert(alertId: string): Promise<void> {
    await apiClient.request<void>(`/api/alerts/${alertId}/`, {
      method: 'DELETE',
    })
  }

  async toggleAlert(alertId: string, enabled: boolean): Promise<Alert> {
    return this.updateAlert(alertId, { enabled })
  }

  async duplicateAlert(alertId: string, name?: string): Promise<Alert> {
    return apiClient.request<Alert>(`/api/alerts/${alertId}/duplicate/`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    })
  }

  /**
   * Alert templates
   */
  
  async getTemplates(category?: string, search?: string): Promise<AlertTemplate[]> {
    const params = new URLSearchParams()
    if (category) params.append('category', category)
    if (search) params.append('search', search)

    return apiClient.request<AlertTemplate[]>(`/api/alert-templates/?${params}`)
  }

  async getTemplate(templateId: string): Promise<AlertTemplate> {
    return apiClient.request<AlertTemplate>(`/api/alert-templates/${templateId}/`)
  }

  async createTemplate(template: Omit<AlertTemplate, 'id' | 'created_at' | 'updated_at' | 'usage_count' | 'rating' | 'reviews_count'>): Promise<AlertTemplate> {
    return apiClient.request<AlertTemplate>('/api/alert-templates/', {
      method: 'POST',
      body: JSON.stringify(template),
    })
  }

  async updateTemplate(templateId: string, data: Partial<AlertTemplate>): Promise<AlertTemplate> {
    return apiClient.request<AlertTemplate>(`/api/alert-templates/${templateId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async deleteTemplate(templateId: string): Promise<void> {
    await apiClient.request<void>(`/api/alert-templates/${templateId}/`, {
      method: 'DELETE',
    })
  }

  /**
   * Alert execution and monitoring
   */
  
  async getAlertExecutions(
    alertId: string,
    limit = 50,
    offset = 0
  ): Promise<{ executions: AlertExecution[], total: number }> {
    return apiClient.request<{ executions: AlertExecution[], total: number }>(
      `/api/alerts/${alertId}/executions/?limit=${limit}&offset=${offset}`
    )
  }

  async getAlertMetrics(alertId: string, period = '7d'): Promise<AlertMetrics> {
    return apiClient.request<AlertMetrics>(`/api/alerts/${alertId}/metrics/?period=${period}`)
  }

  async testAlert(alertId: string, testData?: any): Promise<{
    success: boolean
    result?: any
    execution_time_ms: number
    error?: string
  }> {
    return apiClient.request<{
      success: boolean
      result?: any
      execution_time_ms: number
      error?: string
    }>(`/api/alerts/${alertId}/test/`, {
      method: 'POST',
      body: JSON.stringify({ test_data: testData }),
    })
  }

  async triggerAlert(alertId: string, triggerData?: any): Promise<{
    execution_id: string
    status: string
  }> {
    return apiClient.request<{
      execution_id: string
      status: string
    }>(`/api/alerts/${alertId}/trigger/`, {
      method: 'POST',
      body: JSON.stringify({ trigger_data: triggerData }),
    })
  }

  /**
   * Notification channels
   */
  
  async getNotificationChannels(teamId?: string): Promise<NotificationChannel[]> {
    const params = teamId ? `?team_id=${teamId}` : ''
    return apiClient.request<NotificationChannel[]>(`/api/notification-channels/${params}`)
  }

  async createNotificationChannel(data: {
    name: string
    type: ChannelType
    configuration: ChannelConfiguration
    team_id?: string
  }): Promise<NotificationChannel> {
    return apiClient.request<NotificationChannel>('/api/notification-channels/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateNotificationChannel(
    channelId: string, 
    data: Partial<NotificationChannel>
  ): Promise<NotificationChannel> {
    return apiClient.request<NotificationChannel>(`/api/notification-channels/${channelId}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async deleteNotificationChannel(channelId: string): Promise<void> {
    await apiClient.request<void>(`/api/notification-channels/${channelId}/`, {
      method: 'DELETE',
    })
  }

  async testNotificationChannel(channelId: string, message?: string): Promise<{
    success: boolean
    message: string
    response_time_ms: number
  }> {
    return apiClient.request<{
      success: boolean
      message: string
      response_time_ms: number
    }>(`/api/notification-channels/${channelId}/test/`, {
      method: 'POST',
      body: JSON.stringify({ message: message || 'Test notification from Ekko Dashboard' }),
    })
  }

  /**
   * Bulk operations
   */
  
  async bulkUpdateAlerts(alertIds: string[], updates: UpdateAlertRequest): Promise<{
    updated: number
    errors: Array<{ alert_id: string, error: string }>
  }> {
    return apiClient.request<{
      updated: number
      errors: Array<{ alert_id: string, error: string }>
    }>('/api/alerts/bulk-update/', {
      method: 'POST',
      body: JSON.stringify({
        alert_ids: alertIds,
        updates,
      }),
    })
  }

  async bulkDeleteAlerts(alertIds: string[]): Promise<{
    deleted: number
    errors: Array<{ alert_id: string, error: string }>
  }> {
    return apiClient.request<{
      deleted: number
      errors: Array<{ alert_id: string, error: string }>
    }>('/api/alerts/bulk-delete/', {
      method: 'POST',
      body: JSON.stringify({ alert_ids: alertIds }),
    })
  }

  /**
   * Export/Import
   */
  
  async exportAlerts(alertIds?: string[]): Promise<Blob> {
    const params = alertIds ? `?alert_ids=${alertIds.join(',')}` : ''
    const response = await fetch(`${apiClient.getBaseURL()}/api/alerts/export/${params}`, {
      headers: {
        'Authorization': `Bearer ${apiClient.getAccessToken()}`,
      },
    })
    return response.blob()
  }

  async importAlerts(file: File): Promise<{
    imported: number
    errors: Array<{ line: number, error: string }>
  }> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${apiClient.getBaseURL()}/api/alerts/import/`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiClient.getAccessToken()}`,
      },
      body: formData,
    })

    return response.json()
  }
}

// Create and export singleton instance
export const alertApiService = new AlertApiService()

// Export the class for testing
export { AlertApiService }
