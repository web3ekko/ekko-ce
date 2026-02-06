/**
 * WebAuthn Service
 * 
 * Handles passkey creation and authentication using the WebAuthn API
 */

import type { WebAuthnSupport } from '../types/auth'

class WebAuthnService {
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
   * Create a new passkey (registration)
   */
  async createPasskey(options: {
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
  }): Promise<{
    id: string
    rawId: string
    response: {
      attestationObject: string
      clientDataJSON: string
    }
    type: 'public-key'
  }> {
    const support = this.checkSupport()
    if (!support.supported) {
      throw new Error('WebAuthn is not supported in this browser')
    }

    const publicKeyCredentialCreationOptions: PublicKeyCredentialCreationOptions = {
      challenge: this.base64UrlToArrayBuffer(options.challenge),
      rp: options.rp,
      user: {
        id: new TextEncoder().encode(options.user.id),
        name: options.user.name,
        displayName: options.user.displayName,
      },
      pubKeyCredParams: [
        { alg: -7, type: 'public-key' }, // ES256
        { alg: -257, type: 'public-key' }, // RS256
      ],
      authenticatorSelection: {
        authenticatorAttachment: 'platform',
        userVerification: 'preferred',
        requireResidentKey: true,
      },
      timeout: options.timeout || 60000,
      attestation: 'none',
    }

    try {
      const credential = await navigator.credentials.create({
        publicKey: publicKeyCredentialCreationOptions,
      }) as PublicKeyCredential

      if (!credential) {
        throw new Error('Failed to create credential')
      }

      const response = credential.response as AuthenticatorAttestationResponse

      return {
        id: credential.id,
        rawId: this.arrayBufferToBase64Url(credential.rawId),
        response: {
          attestationObject: this.arrayBufferToBase64Url(response.attestationObject),
          clientDataJSON: this.arrayBufferToBase64Url(response.clientDataJSON),
        },
        type: 'public-key',
      }
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
      throw new Error('Failed to create passkey: ' + (error as Error).message)
    }
  }

  /**
   * Authenticate with an existing passkey
   */
  async authenticatePasskey(options: {
    challenge: string
    rpId: string
    allowCredentials?: Array<{
      id: string
      type: 'public-key'
    }>
    timeout?: number
    conditionalMediation?: boolean
  }): Promise<{
    id: string
    rawId: string
    response: {
      authenticatorData: string
      clientDataJSON: string
      signature: string
      userHandle?: string
    }
    type: 'public-key'
  }> {
    const support = this.checkSupport()
    if (!support.supported) {
      throw new Error('WebAuthn is not supported in this browser')
    }

    const allowCredentials = options.allowCredentials?.map(cred => ({
      id: this.base64UrlToArrayBuffer(cred.id),
      type: cred.type as const,
    }))

    const publicKeyCredentialRequestOptions: PublicKeyCredentialRequestOptions = {
      challenge: this.base64UrlToArrayBuffer(options.challenge),
      rpId: options.rpId,
      allowCredentials,
      userVerification: 'preferred',
      timeout: options.timeout || 60000,
    }

    const credentialRequestOptions: CredentialRequestOptions = {
      publicKey: publicKeyCredentialRequestOptions,
    }

    // Add conditional mediation if supported and requested
    if (options.conditionalMediation && support.conditionalMediation) {
      credentialRequestOptions.mediation = 'conditional'
    }

    try {
      // Add a manual timeout wrapper for better control
      const timeoutMs = options.timeout || 60000
      
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

      const response = credential.response as AuthenticatorAssertionResponse

      return {
        id: credential.id,
        rawId: this.arrayBufferToBase64Url(credential.rawId),
        response: {
          authenticatorData: this.arrayBufferToBase64Url(response.authenticatorData),
          clientDataJSON: this.arrayBufferToBase64Url(response.clientDataJSON),
          signature: this.arrayBufferToBase64Url(response.signature),
          userHandle: response.userHandle ? this.arrayBufferToBase64Url(response.userHandle) : undefined,
        },
        type: 'public-key',
      }
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
      throw new Error('Failed to authenticate with passkey: ' + (error as Error).message)
    }
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
}

// Create and export a singleton instance
export const webAuthnService = new WebAuthnService()

// Export the class for testing
export { WebAuthnService }
