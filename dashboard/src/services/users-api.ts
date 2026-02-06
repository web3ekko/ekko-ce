/**
 * Users API Service
 *
 * API calls for user profile management
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS } from '../config/api'

// Types
export interface UserProfile {
  id: string
  email: string
  name: string
  display_name?: string
  avatar_url?: string
  bio?: string
  role: string
  is_active: boolean
  created_at: string
  last_login?: string
  has_passkey?: boolean
  two_factor_enabled?: boolean
  timezone?: string
  language?: string
}

export interface NotificationPreferences {
  email_alerts: boolean
  push_notifications: boolean
  alert_digest: 'instant' | 'daily' | 'weekly' | 'none'
  marketing_emails: boolean
  security_alerts: boolean
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system'
  dashboard_layout?: string
  default_network?: string
  notification_preferences: NotificationPreferences
}

export interface UpdateProfileRequest {
  name?: string
  display_name?: string
  bio?: string
  timezone?: string
  language?: string
}

export interface UpdatePreferencesRequest {
  theme?: 'light' | 'dark' | 'system'
  dashboard_layout?: string
  default_network?: string
  notification_preferences?: Partial<NotificationPreferences>
}

export interface ConnectedService {
  id: string
  service_type: 'slack' | 'telegram' | 'discord' | 'github'
  connected_at: string
  account_name?: string
  is_active: boolean
}

export interface ActiveSession {
  id: string
  device_type: string
  device_name: string
  ip_address: string
  location?: string
  last_active: string
  is_current: boolean
  created_at: string
}

export interface ExportDataResponse {
  download_url: string
  expires_at: string
  file_size: number
}

class UsersApiService {
  // Get current user profile
  async getProfile(): Promise<UserProfile> {
    try {
      const response = await httpClient.get<UserProfile>(API_ENDPOINTS.PROFILE.GET)
      return response.data
    } catch (error: any) {
      console.error('Get profile failed:', error)
      throw error
    }
  }

  // Update user profile
  async updateProfile(data: UpdateProfileRequest): Promise<UserProfile> {
    try {
      const response = await httpClient.patch<UserProfile>(
        API_ENDPOINTS.PROFILE.UPDATE,
        data
      )
      return response.data
    } catch (error: any) {
      console.error('Update profile failed:', error)
      throw error
    }
  }

  // Upload avatar
  async uploadAvatar(file: File): Promise<{ avatar_url: string }> {
    try {
      const formData = new FormData()
      formData.append('avatar', file)

      const response = await httpClient.post<{ avatar_url: string }>(
        API_ENDPOINTS.PROFILE.AVATAR,
        formData,
        { 'Content-Type': 'multipart/form-data' }
      )
      return response.data
    } catch (error: any) {
      console.error('Upload avatar failed:', error)
      throw error
    }
  }

  // Delete avatar
  async deleteAvatar(): Promise<void> {
    try {
      await httpClient.delete(API_ENDPOINTS.PROFILE.AVATAR)
    } catch (error: any) {
      console.error('Delete avatar failed:', error)
      throw error
    }
  }

  // Get user preferences
  async getPreferences(): Promise<UserPreferences> {
    try {
      const response = await httpClient.get<UserPreferences>(
        API_ENDPOINTS.PROFILE.PREFERENCES
      )
      return response.data
    } catch (error: any) {
      console.error('Get preferences failed:', error)
      throw error
    }
  }

  // Update user preferences
  async updatePreferences(data: UpdatePreferencesRequest): Promise<UserPreferences> {
    try {
      const response = await httpClient.patch<UserPreferences>(
        API_ENDPOINTS.PROFILE.PREFERENCES,
        data
      )
      return response.data
    } catch (error: any) {
      console.error('Update preferences failed:', error)
      throw error
    }
  }

  // Get connected services
  async getConnectedServices(): Promise<ConnectedService[]> {
    try {
      const response = await httpClient.get<{ services: ConnectedService[] }>(
        API_ENDPOINTS.PROFILE.CONNECTED_SERVICES
      )
      return response.data.services
    } catch (error: any) {
      console.error('Get connected services failed:', error)
      throw error
    }
  }

  // Disconnect a service
  async disconnectService(serviceId: string): Promise<void> {
    try {
      await httpClient.delete(API_ENDPOINTS.PROFILE.CONNECTED_SERVICE_DETAIL(serviceId))
    } catch (error: any) {
      console.error('Disconnect service failed:', error)
      throw error
    }
  }

  // Get active sessions
  async getActiveSessions(): Promise<ActiveSession[]> {
    try {
      const response = await httpClient.get<{ sessions: ActiveSession[] }>(
        API_ENDPOINTS.PROFILE.SESSIONS
      )
      return response.data.sessions
    } catch (error: any) {
      console.error('Get active sessions failed:', error)
      throw error
    }
  }

  // Revoke a session
  async revokeSession(sessionId: string): Promise<void> {
    try {
      await httpClient.delete(API_ENDPOINTS.PROFILE.SESSION_DETAIL(sessionId))
    } catch (error: any) {
      console.error('Revoke session failed:', error)
      throw error
    }
  }

  // Revoke all other sessions
  async revokeAllOtherSessions(): Promise<void> {
    try {
      await httpClient.post(API_ENDPOINTS.PROFILE.SESSIONS_REVOKE_ALL)
    } catch (error: any) {
      console.error('Revoke all sessions failed:', error)
      throw error
    }
  }

  // Request data export
  async requestDataExport(): Promise<ExportDataResponse> {
    try {
      const response = await httpClient.post<ExportDataResponse>(
        API_ENDPOINTS.PROFILE.EXPORT_DATA
      )
      return response.data
    } catch (error: any) {
      console.error('Request data export failed:', error)
      throw error
    }
  }

  // Delete account
  async deleteAccount(confirmation: string): Promise<void> {
    try {
      await httpClient.post(API_ENDPOINTS.PROFILE.DELETE_ACCOUNT, {
        confirmation,
      })
    } catch (error: any) {
      console.error('Delete account failed:', error)
      throw error
    }
  }

}

export const usersApiService = new UsersApiService()
export default usersApiService
