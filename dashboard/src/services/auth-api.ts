/**
 * Authentication API Service
 * 
 * API calls for passwordless authentication
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS } from '../config/api'

// Types
export interface User {
  id: string
  email: string
  name: string
  role: string
  is_active: boolean
  created_at: string
  last_login?: string
  has_passkey?: boolean
  firebase_uid?: string
}

// Legacy magic link interfaces (kept for compatibility)
export interface SendMagicLinkRequest {
  email: string
}

export interface SendMagicLinkResponse {
  message: string
  email: string
}

export interface VerifyMagicLinkRequest {
  token: string
}

export interface VerifyMagicLinkResponse {
  user: User
  access_token: string
  refresh_token: string
}

// New verification code interfaces
export interface CheckAccountRequest {
  email: string
}

export interface CheckAccountResponse {
  exists: boolean
  message: string
  status?: 'no_account' | 'inactive_account' | 'active_account'
}

export interface SignupRequest {
  email: string
}

export interface SignupResponse {
  success: boolean
  message: string
  code_sent: boolean
  retry_after?: number
}

export interface VerifyCodeRequest {
  email: string
  code: string
}

export interface VerifyCodeResponse {
  success: boolean
  message: string
  passkey_required?: boolean
  next_step?: string
  token?: string
  user?: User
}

export interface SendCodeRequest {
  email: string
}

export interface SendCodeResponse {
  success: boolean
  message: string
}

export interface ResendCodeRequest {
  email: string
  purpose: 'signup' | 'signin' | 'recovery'
}

export interface ResendCodeResponse {
  success: boolean
  message: string
  retry_after?: number
}

export interface PasskeyChallengeRequest {
  email: string
}

export interface PasskeyChallengeResponse {
  challenge: string
  user_id: string
  options: any // WebAuthn options
}

export interface PasskeyVerifyRequest {
  email: string
  challenge: string
  credential: any // WebAuthn credential
}

export interface PasskeyVerifyResponse {
  user: User
  access_token: string
  refresh_token: string
}

export interface PasskeyRegistrationOptionsResponse {
  success: boolean
  options: {
    publicKey: {
      challenge: string
      user: {
        id: string
        name: string
        displayName: string
      }
      rp: {
        name: string
        id: string
      }
      timeout?: number
      pubKeyCredParams: Array<{
        type: string
        alg: number
      }>
      excludeCredentials?: Array<any>
      authenticatorSelection?: {
        residentKey?: string
        userVerification?: string
        requireResidentKey?: boolean
      }
      extensions?: any
    }
  }
  message?: string
}

export interface MeResponse {
  user: User
}

class AuthApiService {
  // ========== New Verification Code Methods ==========
  
  // Check if account exists
  async checkAccountStatus(email: string): Promise<CheckAccountResponse> {
    try {
      const response = await httpClient.post<CheckAccountResponse>(
        '/api/auth/check-account-status/',
        { email }
      )
      return response.data
    } catch (error: any) {
      console.error('Check account status failed:', error)
      throw error
    }
  }

  // Start signup process
  async signup(email: string): Promise<SignupResponse> {
    try {
      const response = await httpClient.post<SignupResponse>(
        '/api/auth/signup/',
        { email }
      )
      return response.data
    } catch (error: any) {
      console.error('Signup failed:', error)
      throw error
    }
  }

  // Verify signup code
  async verifySignupCode(email: string, code: string): Promise<VerifyCodeResponse> {
    try {
      const response = await httpClient.post<VerifyCodeResponse>(
        '/api/auth/signup/verify-code/',
        { email, code }
      )
      
      // Store the token if provided
      if (response.data.token) {
        httpClient.setAuthToken(response.data.token)
      }
      
      return response.data
    } catch (error: any) {
      console.error('Verify signup code failed:', error)
      throw error
    }
  }

  // Send signin code
  async sendSigninCode(email: string): Promise<SendCodeResponse> {
    try {
      const response = await httpClient.post<SendCodeResponse>(
        '/api/auth/signin/email/send-code/',
        { email }
      )
      return response.data
    } catch (error: any) {
      console.error('Send signin code failed:', error)
      throw error
    }
  }

  // Verify signin code
  async verifySigninCode(email: string, code: string): Promise<VerifyCodeResponse> {
    try {
      const response = await httpClient.post<VerifyCodeResponse>(
        '/api/auth/signin/email/verify-code/',
        { email, code }
      )
      
      // Store the token if provided
      if (response.data.token) {
        httpClient.setAuthToken(response.data.token)
      }
      
      return response.data
    } catch (error: any) {
      console.error('Verify signin code failed:', error)
      throw error
    }
  }

  // Resend verification code
  async resendCode(email: string, purpose: 'signup' | 'signin' | 'recovery'): Promise<ResendCodeResponse> {
    try {
      const response = await httpClient.post<ResendCodeResponse>(
        '/api/auth/resend-code/',
        { email, purpose }
      )
      return response.data
    } catch (error: any) {
      console.error('Resend code failed:', error)
      throw error
    }
  }

  // Request account recovery
  async requestRecovery(email: string): Promise<SendCodeResponse> {
    try {
      const response = await httpClient.post<SendCodeResponse>(
        '/api/auth/recovery/request/',
        { email }
      )
      return response.data
    } catch (error: any) {
      console.error('Request recovery failed:', error)
      throw error
    }
  }

  // Verify recovery code
  async verifyRecoveryCode(email: string, code: string): Promise<VerifyCodeResponse> {
    try {
      const response = await httpClient.post<VerifyCodeResponse>(
        '/api/auth/recovery/verify-code/',
        { email, code }
      )
      return response.data
    } catch (error: any) {
      console.error('Verify recovery code failed:', error)
      throw error
    }
  }

  // Get passkey registration options
  async getPasskeyRegistrationOptions(): Promise<PasskeyRegistrationOptionsResponse> {
    try {
      const response = await httpClient.post<PasskeyRegistrationOptionsResponse>(
        '/api/auth/signup/passkey/register/'
      )
      return response.data
    } catch (error: any) {
      console.error('Get passkey registration options failed:', error)
      throw error
    }
  }

  // Complete passkey registration
  async completePasskeyRegistration(email: string, credential: any): Promise<VerifyCodeResponse> {
    try {
      const response = await httpClient.post<VerifyCodeResponse>(
        '/api/auth/signup/passkey/register/',
        { email, credential_data: credential }
      )
      
      // Store the token if provided
      if (response.data.token) {
        httpClient.setAuthToken(response.data.token)
      }
      
      return response.data
    } catch (error: any) {
      console.error('Complete passkey registration failed:', error)
      throw error
    }
  }

  // Complete signup without passkey (development mode)
  async completeSignupDev(): Promise<VerifyCodeResponse> {
    try {
      const response = await httpClient.post<VerifyCodeResponse>(
        '/api/auth/signup/complete-dev/'
      )
      
      return response.data
    } catch (error: any) {
      console.error('Complete signup dev failed:', error)
      throw error
    }
  }

  // Skip passkey creation during signup
  async skipPasskeyCreation(): Promise<VerifyCodeResponse> {
    try {
      const response = await httpClient.post<VerifyCodeResponse>(
        '/api/auth/signup/passkey/skip/'
      )
      
      return response.data
    } catch (error: any) {
      console.error('Skip passkey creation failed:', error)
      throw error
    }
  }

  // ========== Legacy Magic Link Methods (kept for compatibility) ==========
  
  // Send magic link to email
  async sendMagicLink(email: string): Promise<SendMagicLinkResponse> {
    try {
      const response = await httpClient.post<SendMagicLinkResponse>(
        API_ENDPOINTS.AUTH.SEND_MAGIC_LINK,
        { email }
      )
      return response.data
    } catch (error: any) {
      console.error('Send magic link failed:', error)
      throw error
    }
  }

  // Verify magic link token
  async verifyMagicLink(token: string): Promise<VerifyMagicLinkResponse> {
    try {
      const response = await httpClient.post<VerifyMagicLinkResponse>(
        API_ENDPOINTS.AUTH.VERIFY_MAGIC_LINK,
        { token }
      )
      
      // Store the access token
      if (response.data.access_token) {
        httpClient.setAuthToken(response.data.access_token)
      }
      
      return response.data
    } catch (error: any) {
      console.error('Verify magic link failed:', error)
      throw error
    }
  }

  // Get passkey challenge
  async getPasskeyChallenge(email: string): Promise<PasskeyChallengeResponse> {
    try {
      const response = await httpClient.post<PasskeyChallengeResponse>(
        API_ENDPOINTS.AUTH.PASSKEY_CHALLENGE,
        { email }
      )
      return response.data
    } catch (error: any) {
      console.error('Get passkey challenge failed:', error)
      throw error
    }
  }

  // Verify passkey credential
  async verifyPasskey(email: string, challenge: string, credential: any): Promise<PasskeyVerifyResponse> {
    try {
      const response = await httpClient.post<PasskeyVerifyResponse>(
        API_ENDPOINTS.AUTH.PASSKEY_VERIFY,
        { email, challenge, credential }
      )
      
      // Store the access token
      if (response.data.access_token) {
        httpClient.setAuthToken(response.data.access_token)
      }
      
      return response.data
    } catch (error: any) {
      console.error('Verify passkey failed:', error)
      throw error
    }
  }

  // Get current user
  async getCurrentUser(): Promise<User> {
    try {
      const response = await httpClient.get<MeResponse>(API_ENDPOINTS.AUTH.ME)
      return response.data.user
    } catch (error: any) {
      console.error('Get current user failed:', error)
      throw error
    }
  }

  // Logout
  async logout(): Promise<void> {
    try {
      await httpClient.post(API_ENDPOINTS.AUTH.LOGOUT)
    } catch (error: any) {
      console.error('Logout failed:', error)
      // Don't throw error for logout - always clear local token
    } finally {
      // Always clear the local token
      httpClient.clearAuthToken()
    }
  }

  // Check if user is authenticated (has valid token)
  isAuthenticated(): boolean {
    const token = localStorage.getItem('ekko-auth-token')
    return !!token
  }

}

export const authApiService = new AuthApiService()
export default authApiService
