/**
 * Authentication Types
 * 
 * TypeScript interfaces for authentication-related data structures
 * that match the Django API responses
 */

export interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  preferred_auth_method: 'passkey' | 'email'
  is_email_verified: boolean
  has_passkey: boolean
  has_2fa: boolean
  created_at: string
  last_login: string | null
}

export interface Device {
  id: string
  user: string
  device_name: string
  device_type: 'web' | 'mobile' | 'desktop'
  platform: string
  browser: string
  device_id: string
  supports_passkey: boolean
  supports_biometric: boolean
  is_trusted: boolean
  is_active: boolean
  trust_expires_at: string | null
  last_used_at: string
  created_at: string
}

export interface AuthTokens {
  access: string
  refresh: string
}

// Signup Flow Types
export interface SignupBeginRequest {
  email: string
  device_info?: {
    webauthn_supported?: boolean
    device_type?: string
    platform?: string
    browser?: string
  }
}

export interface SignupBeginResponse {
  email: string
  auth_options: Array<{
    method: string
    supported: boolean
    recommended: boolean
  }>
  recommended_method: string
  message: string
  next_step: 'verify_email'
}

export interface SignupCompleteRequest {
  token: string
  device_info?: {
    webauthn_supported?: boolean
    device_type?: string
    platform?: string
    browser?: string
  }
  credential_data?: {
    id: string
    rawId: string
    response: {
      attestationObject: string
      clientDataJSON: string
    }
    type: 'public-key'
  }
}

export interface SignupCompleteResponse {
  user: User
  tokens: AuthTokens
  device: Device
  setup_complete: boolean
  next_steps: string[]
}

// Login Flow Types
export interface LoginRequest {
  email: string
  auth_method?: 'auto' | 'passkey' | 'email_magic_link'
  device_info?: {
    webauthn_supported?: boolean
    device_type?: string
    platform?: string
    browser?: string
  }
}

export interface LoginResponse {
  method: string
  challenge?: {
    // WebAuthn challenge data
    challenge: string
    timeout: number
    rpId: string
    allowCredentials: Array<{
      id: string
      type: 'public-key'
    }>
  }
  magic_link_sent?: boolean
  message: string
  next_step: 'passkey_auth' | 'magic_link_sent' | 'complete'
}

export interface PasskeyAuthRequest {
  credential_data: {
    id: string
    rawId: string
    response: {
      authenticatorData: string
      clientDataJSON: string
      signature: string
      userHandle?: string
    }
    type: 'public-key'
  }
}

export interface MagicLinkVerifyRequest {
  token: string
}

export interface AuthSuccessResponse {
  user: User
  tokens: AuthTokens
  device: Device
  message: string
}

// Recovery Types
export interface RecoveryRequest {
  email: string
}

export interface RecoveryResponse {
  email: string
  message: string
  next_step: 'check_email'
}

// Device Management Types
export interface DeviceListResponse {
  devices: Device[]
  current_device_id: string
}

// Error Types
export interface AuthError {
  error: string
  details?: Record<string, string[]>
  code?: string
}

// WebAuthn Types
export interface WebAuthnSupport {
  supported: boolean
  conditionalMediation: boolean
  platform: boolean
  crossPlatform: boolean
}

// Auth State Types
export interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  tokens: AuthTokens | null
}

// Form Types
export interface SignupFormData {
  email: string
  first_name: string
  last_name: string
  agree_to_terms: boolean
}

export interface LoginFormData {
  email: string
  remember_device: boolean
}

// API Response wrapper
export interface ApiResponse<T> {
  data?: T
  error?: AuthError
  success: boolean
}

// Firebase Integration Types
export interface FirebaseUser {
  uid: string
  email: string
  displayName?: string
  emailVerified: boolean
  photoURL?: string
}

export interface TokenExchangeRequest {
  firebase_token: string
  device_info: {
    device_type: 'web' | 'mobile' | 'desktop'
    platform: string
    user_agent: string
    webauthn_supported: boolean
  }
}

export interface TokenExchangeResponse {
  access_token: string
  refresh_token: string
  user: User
  session?: {
    session_id: string
    device_trusted: boolean
    expires_at: string
  }
  auth_method: 'firebase'
  recovery_codes?: string[]
  message?: string
}

export interface FirebaseConfig {
  apiKey: string
  authDomain: string
  projectId: string
  storageBucket?: string
  messagingSenderId?: string
  appId?: string
}

export interface AuthCapabilities {
  webauthn: boolean
  firebase: boolean
  email_link: boolean
  email_password: boolean
  social_login: boolean
  biometric: boolean
}

export type AuthMethod = 'webauthn' | 'firebase' | 'email' | 'passkey'
export type AuthMode = 'signin' | 'signup'
