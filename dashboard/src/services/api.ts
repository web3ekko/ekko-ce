/**
 * API Service
 * 
 * Centralized API client for communicating with the Django backend
 */

import type {
  SignupBeginRequest,
  SignupBeginResponse,
  SignupCompleteRequest,
  SignupCompleteResponse,
  LoginRequest,
  LoginResponse,
  PasskeyAuthRequest,
  MagicLinkVerifyRequest,
  AuthSuccessResponse,
  RecoveryRequest,
  RecoveryResponse,
  User,
  Device,
  DeviceListResponse,
  AuthError,
} from '../types/auth'

class ApiClient {
  private baseURL: string
  private accessToken: string | null = null

  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  }

  /**
   * Set the access token for authenticated requests
   */
  setAccessToken(token: string | null) {
    this.accessToken = token
  }

  /**
   * Get the current access token
   */
  getAccessToken(): string | null {
    return this.accessToken
  }

  /**
   * Make an HTTP request with proper error handling
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`


    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    // Add authorization header if we have a token
    // Knox uses "Token" prefix, not "Bearer"
    if (this.accessToken) {
      headers.Authorization = `Token ${this.accessToken}`
    }

    const config: RequestInit = {
      ...options,
      headers,
    }

    try {
      const response = await fetch(url, config)


      // Handle different response types
      const contentType = response.headers.get('content-type')
      let data: any

      if (contentType && contentType.includes('application/json')) {
        data = await response.json()
      } else {
        data = await response.text()
      }

      if (!response.ok) {
        // Handle API errors
        const error: AuthError = {
          error: data.error || data.detail || 'An error occurred',
          details: data.details,
          code: data.code,
        }
        throw error
      }

      return data
    } catch (error) {
      // Handle network errors
      if (error instanceof TypeError) {
        throw {
          error: 'Network error. Please check your connection.',
          code: 'NETWORK_ERROR',
        } as AuthError
      }

      // Re-throw API errors
      throw error
    }
  }

  /**
   * Authentication endpoints
   */
  
  // Signup flow
  async signupBegin(data: SignupBeginRequest): Promise<SignupBeginResponse> {
    return this.request<SignupBeginResponse>('/api/auth/signup/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async signupVerifyCode(data: { email: string; code: string }): Promise<SignupCompleteResponse> {
    return this.request<SignupCompleteResponse>('/api/auth/signup/verify-code/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Legacy alias for signupVerifyCode
  async signupComplete(data: SignupCompleteRequest): Promise<SignupCompleteResponse> {
    return this.signupVerifyCode({ email: data.email, code: data.code })
  }

  // Get auth options for an email (check if user exists, has passkeys, etc.)
  async getAuthOptions(email: string): Promise<{ has_account: boolean; has_passkey: boolean; auth_methods: string[] }> {
    return this.request('/api/auth/options/', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
  }

  // Sign-in flow - Passkey
  async signinPasskeyBegin(data: { email: string }): Promise<{ challenge: string; allowCredentials: any[]; rpId: string }> {
    return this.request('/api/auth/signin/passkey/begin/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async signinPasskeyComplete(data: PasskeyAuthRequest): Promise<AuthSuccessResponse> {
    return this.request<AuthSuccessResponse>('/api/auth/signin/passkey/complete/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Legacy alias for signinPasskeyComplete
  async authenticatePasskey(data: PasskeyAuthRequest): Promise<AuthSuccessResponse> {
    return this.signinPasskeyComplete(data)
  }

  // Sign-in flow - Email code
  async signinEmailSendCode(data: { email: string }): Promise<{ message: string; expires_in: number }> {
    return this.request('/api/auth/signin/email/send-code/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async signinEmailVerifyCode(data: { email: string; code: string }): Promise<AuthSuccessResponse> {
    return this.request<AuthSuccessResponse>('/api/auth/signin/email/verify-code/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Legacy alias for signinEmailVerifyCode
  async verifyMagicLink(data: MagicLinkVerifyRequest): Promise<AuthSuccessResponse> {
    return this.signinEmailVerifyCode({ email: data.email, code: data.token || data.code || '' })
  }

  // Resend verification code (works for both signup and signin)
  async resendCode(data: { email: string; flow?: 'signup' | 'signin' }): Promise<{ message: string }> {
    return this.request('/api/auth/resend-code/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Legacy login method - redirects to appropriate flow
  async login(data: LoginRequest): Promise<LoginResponse> {
    // Check what auth options are available for this email
    const options = await this.getAuthOptions(data.email)

    if (options.has_passkey) {
      // Start passkey flow
      return this.signinPasskeyBegin({ email: data.email }) as unknown as LoginResponse
    } else {
      // Start email code flow
      return this.signinEmailSendCode({ email: data.email }) as unknown as LoginResponse
    }
  }

  // Passkey Management
  async registerPasskey(data: { credential_data: any; device_info?: any }): Promise<{ success: boolean; passkey_id: string }> {
    return this.request('/api/auth/passkey/register/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async listPasskeys(): Promise<{ passkeys: any[]; count: number }> {
    return this.request('/api/auth/passkey/list/', {
      method: 'GET',
    })
  }

  async deletePasskey(passkeyId: number): Promise<{ success: boolean; message: string }> {
    return this.request(`/api/auth/passkey/${passkeyId}/delete/`, {
      method: 'DELETE',
    })
  }

  // Recovery
  async requestRecovery(data: RecoveryRequest): Promise<RecoveryResponse> {
    return this.request<RecoveryResponse>('/api/auth/recovery/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Logout
  async logout(): Promise<void> {
    await this.request<void>('/api/auth/logout/', {
      method: 'POST',
    })
  }

  /**
   * User endpoints
   */
  
  async getUserProfile(): Promise<User> {
    return this.request<User>('/api/auth/profile/')
  }

  async updateUserProfile(data: Partial<User>): Promise<User> {
    return this.request<User>('/api/auth/profile/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  /**
   * Device endpoints
   */
  
  async getDevices(): Promise<DeviceListResponse> {
    return this.request<DeviceListResponse>('/api/auth/devices/')
  }

  async deleteDevice(deviceId: string): Promise<void> {
    await this.request<void>(`/api/auth/devices/${deviceId}/`, {
      method: 'DELETE',
    })
  }

  /**
   * Token management
   */

  /**
   * Validate if the current Knox token is still valid.
   * Used on app startup and protected route access.
   * Returns user info if valid, throws 401 if expired/invalid.
   */
  async validateToken(): Promise<{ valid: boolean; user: User }> {
    return this.request<{ valid: boolean; user: User }>('/api/auth/validate-token/', {
      method: 'GET',
    })
  }

  async refreshToken(refreshToken: string): Promise<{ access: string; refresh?: string }> {
    return this.request<{ access: string; refresh?: string }>('/api/auth/token/refresh/', {
      method: 'POST',
      body: JSON.stringify({ refresh: refreshToken }),
    })
  }

  async getFirebaseToken(): Promise<{ firebase_token: string; expires_in: number }> {
    return this.request<{ firebase_token: string; expires_in: number }>('/api/auth/firebase-token/')
  }

  /**
   * Health check
   */
  
  async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/health/')
  }
}

// Create and export a singleton instance
export const apiClient = new ApiClient()

// Export the class for testing
export { ApiClient }
