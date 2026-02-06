/**
 * Authentication Store
 * 
 * Global state management for authentication using Zustand
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { 
  User, 
  AuthTokens, 
  AuthState,
  SignupBeginRequest,
  SignupCompleteRequest,
  LoginRequest,
  RecoveryRequest,
} from '../types/auth'
import { apiClient } from '../services/api'
import { httpClient } from '../services/http-client'
import { webAuthnService } from '../services/webauthn'
import { useWebSocketStore } from './websocket'

interface AuthStore extends AuthState {
  // Actions
  signup: (email: string, deviceInfo?: any) => Promise<{ success: boolean; message: string }>
  completeSignup: (data: SignupCompleteRequest) => Promise<{ success: boolean; user?: User }>
  login: (email: string, deviceInfo?: any) => Promise<{ success: boolean; method?: string; challenge?: any }>
  authenticateWithPasskey: (challenge: any) => Promise<{ success: boolean; user?: User }>
  verifyMagicLink: (token: string) => Promise<{ success: boolean; user?: User }>
  requestRecovery: (email: string) => Promise<{ success: boolean; message: string }>
  logout: () => Promise<void>
  refreshToken: () => Promise<boolean>
  validateSession: () => Promise<boolean>
  getFirebaseToken: () => Promise<string | null>
  clearError: () => void
  setLoading: (loading: boolean) => void

  // Internal actions
  setUser: (user: User | null) => void
  setTokens: (tokens: AuthTokens | null) => void
  setError: (error: string | null) => void
}

const resetRealtimeState = () => {
  const wsState = useWebSocketStore.getState()
  wsState.disconnect()
  wsState.clearNotifications()
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      tokens: null,

      // Actions
      signup: async (email: string, deviceInfo?: any) => {

        set({ isLoading: true, error: null })

        try {
          const request: SignupBeginRequest = {
            email,
            device_info: {
              webauthn_supported: webAuthnService.checkSupport().supported,
              device_type: 'web',
              platform: navigator.platform,
              browser: navigator.userAgent,
              ...deviceInfo,
            },
          }


          const response = await apiClient.signupBegin(request)


          set({ isLoading: false })
          return {
            success: true,
            message: response.message,
          }
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.error || 'Signup failed' 
          })
          return {
            success: false,
            message: error.error || 'Signup failed',
          }
        }
      },

      completeSignup: async (data: SignupCompleteRequest) => {
        set({ isLoading: true, error: null })
        
        try {
          const response = await apiClient.signupComplete(data)
          
          // Set tokens and user
          apiClient.setAccessToken(response.tokens.access)
          httpClient.setAuthToken(response.tokens.access)

          set({
            user: response.user,
            tokens: response.tokens,
            isAuthenticated: true,
            isLoading: false,
          })

          return {
            success: true,
            user: response.user,
          }
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.error || 'Signup completion failed' 
          })
          return {
            success: false,
          }
        }
      },

      login: async (email: string, deviceInfo?: any) => {
        set({ isLoading: true, error: null })
        
        try {
          const request: LoginRequest = {
            email,
            auth_method: 'auto',
            device_info: {
              webauthn_supported: webAuthnService.checkSupport().supported,
              device_type: 'web',
              platform: navigator.platform,
              browser: navigator.userAgent,
              ...deviceInfo,
            },
          }

          const response = await apiClient.login(request)
          
          set({ isLoading: false })
          
          return {
            success: true,
            method: response.method,
            challenge: response.challenge,
          }
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.error || 'Login failed' 
          })
          return {
            success: false,
          }
        }
      },

      authenticateWithPasskey: async (challenge: any) => {
        set({ isLoading: true, error: null })
        
        try {
          // Use WebAuthn to get credential
          const credential = await webAuthnService.authenticatePasskey({
            challenge: challenge.challenge,
            rpId: challenge.rpId,
            allowCredentials: challenge.allowCredentials,
            timeout: challenge.timeout,
          })

          // Send credential to backend
          const response = await apiClient.authenticatePasskey({
            credential_data: credential,
          })

          // Set tokens and user
          apiClient.setAccessToken(response.tokens.access)
          httpClient.setAuthToken(response.tokens.access)

          set({
            user: response.user,
            tokens: response.tokens,
            isAuthenticated: true,
            isLoading: false,
          })

          return {
            success: true,
            user: response.user,
          }
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.message || 'Passkey authentication failed' 
          })
          return {
            success: false,
          }
        }
      },

      verifyMagicLink: async (token: string) => {
        set({ isLoading: true, error: null })
        
        try {
          const response = await apiClient.verifyMagicLink({ token })

          // Set tokens and user
          apiClient.setAccessToken(response.tokens.access)
          httpClient.setAuthToken(response.tokens.access)

          set({
            user: response.user,
            tokens: response.tokens,
            isAuthenticated: true,
            isLoading: false,
          })

          return {
            success: true,
            user: response.user,
          }
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.error || 'Magic link verification failed' 
          })
          return {
            success: false,
          }
        }
      },

      requestRecovery: async (email: string) => {
        set({ isLoading: true, error: null })
        
        try {
          const response = await apiClient.requestRecovery({ email })
          
          set({ isLoading: false })
          return {
            success: true,
            message: response.message,
          }
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.error || 'Recovery request failed' 
          })
          return {
            success: false,
            message: error.error || 'Recovery request failed',
          }
        }
      },

      logout: async () => {
        set({ isLoading: true })
        
        try {
          await apiClient.logout()
        } catch (error) {
          // Continue with logout even if API call fails
          // Continue with logout even if API call fails
        }

        resetRealtimeState()

        // Clear tokens and user
        apiClient.setAccessToken(null)
        httpClient.clearAuthToken()
        
        set({
          user: null,
          tokens: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        })
      },

      refreshToken: async () => {
        const { tokens } = get()

        if (!tokens?.refresh) {
          return false
        }

        try {
          const response = await apiClient.refreshToken(tokens.refresh)

          const newTokens = {
            access: response.access,
            refresh: response.refresh || tokens.refresh,
          }

          apiClient.setAccessToken(newTokens.access)
          httpClient.setAuthToken(newTokens.access)
          set({ tokens: newTokens })

          return true
        } catch (error) {
          // Refresh failed, logout user
          get().logout()
          return false
        }
      },

      validateSession: async () => {
        const { tokens } = get()

        // No token means not authenticated
        if (!tokens?.access) {
          resetRealtimeState()
          httpClient.clearAuthToken()
          set({ isAuthenticated: false, user: null, tokens: null })
          return false
        }

        try {
          // Validate token with backend
          const response = await apiClient.validateToken()

          // Update user data from backend (in case it changed)
          set({
            user: response.user as User,
            isAuthenticated: true,
          })

          return true
        } catch (error) {
          // Token is invalid/expired - clear auth state
          resetRealtimeState()
          apiClient.setAccessToken(null)
          httpClient.clearAuthToken()
          set({
            isAuthenticated: false,
            user: null,
            tokens: null,
          })
          return false
        }
      },

      getFirebaseToken: async () => {
        try {
          const response = await apiClient.getFirebaseToken()
          return response.firebase_token
        } catch (error) {
          // Firebase token retrieval failed - return null
          return null
        }
      },

      clearError: () => set({ error: null }),
      
      setLoading: (loading: boolean) => set({ isLoading: loading }),
      
      setUser: (user: User | null) => {
        const currentId = get().user?.id
        const nextId = user?.id
        if ((currentId && nextId && currentId !== nextId) || (!nextId && currentId)) {
          resetRealtimeState()
        }
        set({ 
          user, 
          isAuthenticated: !!user 
        })
      },
      
      setTokens: (tokens: AuthTokens | null) => {
        if (!tokens) {
          resetRealtimeState()
        }
        apiClient.setAccessToken(tokens?.access || null)
        if (tokens?.access) {
          httpClient.setAuthToken(tokens.access)
        } else {
          httpClient.clearAuthToken()
        }
        set({ tokens })
      },
      
      setError: (error: string | null) => set({ error }),
    }),
    {
      name: 'ekko-auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        // Set the access token when rehydrating
        if (state?.tokens?.access) {
          apiClient.setAccessToken(state.tokens.access)
          httpClient.setAuthToken(state.tokens.access)
          // Validate token with backend after rehydration completes
          // Use setTimeout to ensure store is fully initialized
          setTimeout(() => {
            state.validateSession?.()
          }, 0)
        }
      },
    }
  )
)
