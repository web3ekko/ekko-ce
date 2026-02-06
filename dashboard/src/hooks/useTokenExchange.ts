/**
 * Token Exchange Hook
 * 
 * Handles exchanging Firebase ID tokens for Django JWT tokens,
 * enabling unified authentication between Firebase UI and Django backend.
 */

import { useState, useCallback } from 'react';
import type { TokenExchangeRequest, TokenExchangeResponse, AuthError } from '../types/auth';

interface UseTokenExchangeReturn {
  exchangeFirebaseToken: (firebaseToken: string) => Promise<TokenExchangeResponse>;
  isLoading: boolean;
  error: AuthError | null;
}

export const useTokenExchange = (): UseTokenExchangeReturn => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<AuthError | null>(null);

  const getDeviceInfo = useCallback(() => {
    const userAgent = navigator.userAgent;
    const platform = navigator.platform;
    
    // Detect device type
    let deviceType: 'web' | 'mobile' | 'desktop' = 'web';
    if (/Mobile|Android|iPhone|iPad/.test(userAgent)) {
      deviceType = 'mobile';
    } else if (/Electron/.test(userAgent)) {
      deviceType = 'desktop';
    }

    // Check WebAuthn support
    const webauthnSupported = !!(
      window.PublicKeyCredential &&
      typeof window.PublicKeyCredential === 'function'
    );

    return {
      device_type: deviceType,
      platform,
      user_agent: userAgent,
      webauthn_supported: webauthnSupported,
    };
  }, []);

  const exchangeFirebaseToken = useCallback(async (firebaseToken: string): Promise<TokenExchangeResponse> => {
    setIsLoading(true);
    setError(null);

    try {
      const deviceInfo = getDeviceInfo();
      
      const requestData: TokenExchangeRequest = {
        firebase_token: firebaseToken,
        device_info: deviceInfo,
      };

      const response = await fetch('/api/auth/firebase/token-exchange/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
      }

      const data: TokenExchangeResponse = await response.json();
      
      console.log('Firebase token exchange successful:', {
        user: data.user.email,
        method: data.auth_method,
        hasRecoveryCodes: !!data.recovery_codes,
      });

      return data;
    } catch (err) {
      const authError: AuthError = {
        error: err instanceof Error ? err.message : 'Token exchange failed',
        code: 'TOKEN_EXCHANGE_ERROR',
      };
      
      setError(authError);
      console.error('Firebase token exchange failed:', authError);
      throw authError;
    } finally {
      setIsLoading(false);
    }
  }, [getDeviceInfo]);

  return {
    exchangeFirebaseToken,
    isLoading,
    error,
  };
};
