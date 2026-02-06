/**
 * New WebAuthn Service for clean python-fido2 backend
 * 
 * Handles passkey creation and authentication using the new API
 */

import type { WebAuthnSupport } from '../types/auth'

interface PasskeyDevice {
  id: string
  name: string
  created_at: string
  last_used_at: string | null
  backup_eligible: boolean
  backup_state: boolean
  is_active: boolean
}

class WebAuthnNewService {
  private apiUrl: string

  constructor() {
    this.apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  }

  /**
   * Check if WebAuthn is supported in the current browser
   */
  checkSupport(): WebAuthnSupport {
    const supported = !!(
      window.PublicKeyCredential &&
      navigator.credentials &&
      navigator.credentials.create &&
      navigator.credentials.get
    )

    let conditionalMediation = false
    let platform = false
    let crossPlatform = false

    if (supported) {
      // Check for conditional mediation (autofill)
      conditionalMediation = !!(
        PublicKeyCredential.isConditionalMediationAvailable &&
        typeof PublicKeyCredential.isConditionalMediationAvailable === 'function'
      )

      // Check for platform authenticator
      platform = !!(
        PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable &&
        typeof PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable === 'function'
      )

      // Cross-platform is generally supported if WebAuthn is supported
      crossPlatform = supported
    }

    return {
      supported,
      conditionalMediation,
      platform,
      crossPlatform,
    }
  }

  /**
   * Convert ArrayBuffer to base64url string
   */
  private arrayBufferToBase64Url(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer)
    let binary = ''
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    return btoa(binary)
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '')
  }

  /**
   * Convert base64url string to ArrayBuffer
   */
  private base64UrlToArrayBuffer(base64url: string): ArrayBuffer {
    // Add padding if needed
    const padding = '='.repeat((4 - (base64url.length % 4)) % 4)
    const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/') + padding
    
    const binary = atob(base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
    return bytes.buffer
  }

  /**
   * Begin passkey registration
   */
  async beginRegistration(authToken: string, platformOnly: boolean = false): Promise<any> {
    const response = await fetch(`${this.apiUrl}/api/passkeys/register/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${authToken}`,
      },
      body: JSON.stringify({
        platform_only: platformOnly,
        device_info: {
          user_agent: navigator.userAgent,
          platform: navigator.platform,
        },
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error || 'Failed to begin registration')
    }

    return response.json()
  }

  /**
   * Create a new passkey (registration)
   */
  async createPasskey(authToken: string, options: any): Promise<PasskeyDevice> {
    const support = this.checkSupport()
    if (!support.supported) {
      throw new Error('WebAuthn is not supported in this browser')
    }

    // Convert challenge and user.id from base64url to ArrayBuffer
    const publicKeyCredentialCreationOptions: PublicKeyCredentialCreationOptions = {
      ...options.publicKey,
      challenge: this.base64UrlToArrayBuffer(options.publicKey.challenge),
      user: {
        ...options.publicKey.user,
        id: this.base64UrlToArrayBuffer(options.publicKey.user.id),
      },
      excludeCredentials: options.publicKey.excludeCredentials?.map((cred: any) => ({
        ...cred,
        id: this.base64UrlToArrayBuffer(cred.id),
      })) || [],
    }

    try {
      const credential = await navigator.credentials.create({
        publicKey: publicKeyCredentialCreationOptions,
      }) as PublicKeyCredential

      if (!credential) {
        throw new Error('Failed to create credential')
      }

      const response = credential.response as AuthenticatorAttestationResponse

      // Complete registration
      const completeResponse = await fetch(`${this.apiUrl}/api/passkeys/register/complete/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Token ${authToken}`,
        },
        body: JSON.stringify({
          credential_data: {
            id: credential.id,
            rawId: this.arrayBufferToBase64Url(credential.rawId),
            response: {
              attestationObject: this.arrayBufferToBase64Url(response.attestationObject),
              clientDataJSON: this.arrayBufferToBase64Url(response.clientDataJSON),
            },
            type: 'public-key',
          },
          device_name: this.getDeviceName(),
        }),
      })

      if (!completeResponse.ok) {
        const error = await completeResponse.json()
        throw new Error(error.error || 'Failed to complete registration')
      }

      const result = await completeResponse.json()
      return result.device
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === 'NotAllowedError') {
          throw new Error('User cancelled passkey creation or operation timed out')
        } else if (error.name === 'InvalidStateError') {
          throw new Error('A passkey already exists for this account')
        } else if (error.name === 'NotSupportedError') {
          throw new Error('Passkeys are not supported on this device')
        }
      }
      throw error
    }
  }

  /**
   * Begin passkey authentication
   */
  async beginAuthentication(email?: string): Promise<any> {
    const response = await fetch(`${this.apiUrl}/api/passkeys/authenticate/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email,
        device_info: {
          user_agent: navigator.userAgent,
          platform: navigator.platform,
        },
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error || 'Failed to begin authentication')
    }

    return response.json()
  }

  /**
   * Authenticate with an existing passkey
   */
  async authenticatePasskey(options: any): Promise<any> {
    const support = this.checkSupport()
    if (!support.supported) {
      throw new Error('WebAuthn is not supported in this browser')
    }

    // Convert challenge from base64url to ArrayBuffer
    const publicKeyCredentialRequestOptions: PublicKeyCredentialRequestOptions = {
      ...options.publicKey,
      challenge: this.base64UrlToArrayBuffer(options.publicKey.challenge),
      allowCredentials: options.publicKey.allowCredentials?.map((cred: any) => ({
        ...cred,
        id: this.base64UrlToArrayBuffer(cred.id),
      })),
    }

    const credentialRequestOptions: CredentialRequestOptions = {
      publicKey: publicKeyCredentialRequestOptions,
    }

    // Add conditional mediation if supported and requested
    if (options.passwordless && support.conditionalMediation) {
      credentialRequestOptions.mediation = 'conditional'
    }

    try {
      // Add a manual timeout wrapper for better control
      const timeoutMs = options.publicKey.timeout || 60000
      
      const credentialPromise = navigator.credentials.get(credentialRequestOptions) as Promise<PublicKeyCredential | null>
      
      // Create a timeout promise
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => {
          reject(new Error('Authentication timed out. No passkeys were selected.'))
        }, timeoutMs)
      })
      
      // Race between credential request and timeout
      const credential = await Promise.race([credentialPromise, timeoutPromise]) as PublicKeyCredential

      if (!credential) {
        throw new Error('No passkey was selected')
      }

      const assertionResponse = credential.response as AuthenticatorAssertionResponse

      // Complete authentication
      const completeResponse = await fetch(`${this.apiUrl}/api/passkeys/authenticate/complete/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          credential_data: {
            id: credential.id,
            rawId: this.arrayBufferToBase64Url(credential.rawId),
            response: {
              authenticatorData: this.arrayBufferToBase64Url(assertionResponse.authenticatorData),
              clientDataJSON: this.arrayBufferToBase64Url(assertionResponse.clientDataJSON),
              signature: this.arrayBufferToBase64Url(assertionResponse.signature),
              userHandle: assertionResponse.userHandle ? this.arrayBufferToBase64Url(assertionResponse.userHandle) : undefined,
            },
            type: 'public-key',
          },
          device_info: {
            user_agent: navigator.userAgent,
            platform: navigator.platform,
          },
        }),
      })

      if (!completeResponse.ok) {
        const error = await completeResponse.json()
        throw new Error(error.error || 'Failed to complete authentication')
      }

      return completeResponse.json()
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === 'NotAllowedError') {
          throw new Error('User cancelled authentication or operation timed out')
        } else if (error.name === 'InvalidStateError') {
          throw new Error('No passkey found for this account')
        } else if (error.name === 'NotSupportedError') {
          throw new Error('Passkeys are not supported on this device')
        }
      }
      throw error
    }
  }

  /**
   * List user's passkey devices
   */
  async listDevices(authToken: string): Promise<PasskeyDevice[]> {
    const response = await fetch(`${this.apiUrl}/api/passkeys/devices/`, {
      headers: {
        'Authorization': `Token ${authToken}`,
      },
    })

    if (!response.ok) {
      throw new Error('Failed to list devices')
    }

    const result = await response.json()
    return result.devices
  }

  /**
   * Delete a passkey device
   */
  async deleteDevice(authToken: string, deviceId: string): Promise<void> {
    const response = await fetch(`${this.apiUrl}/api/passkeys/devices/${deviceId}/delete/`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Token ${authToken}`,
      },
    })

    if (!response.ok) {
      throw new Error('Failed to delete device')
    }
  }

  /**
   * Update device name
   */
  async updateDevice(authToken: string, deviceId: string, name: string): Promise<PasskeyDevice> {
    const response = await fetch(`${this.apiUrl}/api/passkeys/devices/${deviceId}/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${authToken}`,
      },
      body: JSON.stringify({ name }),
    })

    if (!response.ok) {
      throw new Error('Failed to update device')
    }

    const result = await response.json()
    return result.device
  }

  /**
   * Check if conditional mediation is available
   */
  async isConditionalMediationAvailable(): Promise<boolean> {
    if (!PublicKeyCredential.isConditionalMediationAvailable) {
      return false
    }
    
    try {
      return await PublicKeyCredential.isConditionalMediationAvailable()
    } catch {
      return false
    }
  }

  /**
   * Check if platform authenticator is available
   */
  async isPlatformAuthenticatorAvailable(): Promise<boolean> {
    if (!PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable) {
      return false
    }
    
    try {
      return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
    } catch {
      return false
    }
  }

  /**
   * Get a device name based on user agent
   */
  private getDeviceName(): string {
    const ua = navigator.userAgent
    
    // iOS devices
    if (/iPhone/.test(ua)) return 'iPhone'
    if (/iPad/.test(ua)) return 'iPad'
    
    // Android devices
    if (/Android/.test(ua)) return 'Android Device'
    
    // Desktop browsers
    if (/Chrome/.test(ua) && !/Edg/.test(ua)) return 'Chrome on ' + this.getOS()
    if (/Safari/.test(ua) && !/Chrome/.test(ua)) return 'Safari on ' + this.getOS()
    if (/Firefox/.test(ua)) return 'Firefox on ' + this.getOS()
    if (/Edg/.test(ua)) return 'Edge on ' + this.getOS()
    
    return 'Passkey Device'
  }

  /**
   * Get operating system name
   */
  private getOS(): string {
    const ua = navigator.userAgent
    
    if (/Windows/.test(ua)) return 'Windows'
    if (/Mac OS X/.test(ua)) return 'macOS'
    if (/Linux/.test(ua)) return 'Linux'
    if (/Android/.test(ua)) return 'Android'
    if (/iOS|iPhone|iPad/.test(ua)) return 'iOS'
    
    return 'Unknown OS'
  }
}

// Create and export a singleton instance
export const webAuthnNewService = new WebAuthnNewService()

// Export the class for testing
export { WebAuthnNewService }