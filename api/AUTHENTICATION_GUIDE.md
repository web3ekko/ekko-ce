# Ekko Authentication System Guide

## Overview

The Ekko platform implements a passwordless authentication system that prioritizes security and user experience. This guide covers the complete authentication flow, WebAuthn implementation, and security considerations.

## Table of Contents

1. [Authentication Methods](#authentication-methods)
2. [User Registration Flow](#user-registration-flow)
3. [Login Flows](#login-flows)
4. [WebAuthn Implementation](#webauthn-implementation)
5. [Token Management](#token-management)
6. [Security Features](#security-features)
7. [Client Implementation](#client-implementation)
8. [Troubleshooting](#troubleshooting)

## Authentication Methods

### 1. WebAuthn/Passkeys (Primary)

WebAuthn provides phishing-resistant, passwordless authentication using platform authenticators.

**Supported Authenticators:**
- **Platform Authenticators**: Face ID, Touch ID, Windows Hello
- **Cross-Platform Authenticators**: Security keys (YubiKey, etc.)

**Benefits:**
- No passwords to remember or steal
- Phishing-resistant by design
- Built-in two-factor authentication
- Seamless user experience

### 2. Email Verification Codes (Fallback)

Email verification provides a fallback method for:
- Account recovery
- Cross-device authentication
- Users without WebAuthn support

**Features:**
- 6-digit verification codes
- 10-minute expiry
- Rate limiting (5 attempts per code)
- Firebase-powered delivery

## User Registration Flow

### Step 1: Email Collection

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant Firebase
    participant Database

    User->>Frontend: Enter email
    Frontend->>API: POST /auth/signup/begin/
    API->>Database: Check if user exists
    API->>Firebase: Send verification code
    Firebase->>User: Email with 6-digit code
    API->>Frontend: 200 OK
```

**Request:**
```javascript
const response = await fetch('/api/auth/signup/begin/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'user@example.com'
  })
});
```

### Step 2: Email Verification

```javascript
const response = await fetch('/api/auth/signup/verify-email/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'user@example.com',
    code: '123456'
  })
});
```

### Step 3: WebAuthn Registration

```javascript
// Get registration options
const optionsResponse = await fetch('/api/auth/webauthn/register/begin/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'user@example.com'
  })
});

const options = await optionsResponse.json();

// Create credential using WebAuthn API
const credential = await navigator.credentials.create(options);

// Complete registration
const completeResponse = await fetch('/api/auth/webauthn/register/complete/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'user@example.com',
    credential: credential
  })
});

const { knox_token } = await completeResponse.json();
```

## Login Flows

### WebAuthn Login (Primary)

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant Database

    User->>Frontend: Click login
    Frontend->>API: POST /auth/webauthn/login/begin/
    API->>Database: Get user credentials
    API->>Frontend: Challenge & credential IDs
    Frontend->>User: Prompt for biometric
    User->>Frontend: Authenticate (Face ID, etc.)
    Frontend->>API: POST /auth/webauthn/login/complete/
    API->>Database: Verify signature
    API->>Frontend: Knox token
```

### Email Verification Login (Fallback)

Used when:
- User doesn't have passkeys set up
- Accessing from a new device
- WebAuthn is unavailable

```javascript
// Request verification code
await fetch('/api/auth/login/email/', {
  method: 'POST',
  body: JSON.stringify({ email: 'user@example.com' })
});

// Verify code
const response = await fetch('/api/auth/login/verify/', {
  method: 'POST',
  body: JSON.stringify({
    email: 'user@example.com',
    code: '123456'
  })
});
```

## WebAuthn Implementation

### Server-Side Configuration

The server uses Django Allauth MFA for WebAuthn support:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    'allauth',
    'allauth.account',
    'allauth.mfa',
    # ...
]

# WebAuthn configuration
MFA_WEBAUTHN_RP_ID = 'your-domain.com'
MFA_WEBAUTHN_RP_NAME = 'Ekko'
MFA_WEBAUTHN_ATTESTATION = 'none'  # For privacy
MFA_WEBAUTHN_USER_VERIFICATION = 'preferred'
```

### Client-Side Implementation

#### Registration Helper

```javascript
class WebAuthnHelper {
  static async register(email) {
    try {
      // Get options from server
      const optionsRes = await fetch('/api/auth/webauthn/register/begin/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      
      const options = await optionsRes.json();
      
      // Convert base64 strings to ArrayBuffers
      options.publicKey.challenge = this.base64ToArrayBuffer(
        options.publicKey.challenge
      );
      options.publicKey.user.id = this.base64ToArrayBuffer(
        options.publicKey.user.id
      );
      
      // Create credential
      const credential = await navigator.credentials.create(options);
      
      // Convert ArrayBuffers to base64 for transmission
      const credentialJSON = {
        id: credential.id,
        rawId: this.arrayBufferToBase64(credential.rawId),
        response: {
          attestationObject: this.arrayBufferToBase64(
            credential.response.attestationObject
          ),
          clientDataJSON: this.arrayBufferToBase64(
            credential.response.clientDataJSON
          )
        },
        type: credential.type
      };
      
      // Complete registration
      const completeRes = await fetch('/api/auth/webauthn/register/complete/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          credential: credentialJSON
        })
      });
      
      return await completeRes.json();
    } catch (error) {
      console.error('WebAuthn registration failed:', error);
      throw error;
    }
  }
  
  static base64ToArrayBuffer(base64) {
    const binaryString = window.atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  }
  
  static arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }
}
```

#### Login Helper

```javascript
static async login(email) {
  try {
    // Get authentication options
    const optionsRes = await fetch('/api/auth/webauthn/login/begin/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    
    const options = await optionsRes.json();
    
    // Convert challenge
    options.publicKey.challenge = this.base64ToArrayBuffer(
      options.publicKey.challenge
    );
    
    // Convert credential IDs
    for (let cred of options.publicKey.allowCredentials) {
      cred.id = this.base64ToArrayBuffer(cred.id);
    }
    
    // Get assertion
    const assertion = await navigator.credentials.get(options);
    
    // Convert for transmission
    const assertionJSON = {
      id: assertion.id,
      rawId: this.arrayBufferToBase64(assertion.rawId),
      response: {
        authenticatorData: this.arrayBufferToBase64(
          assertion.response.authenticatorData
        ),
        clientDataJSON: this.arrayBufferToBase64(
          assertion.response.clientDataJSON
        ),
        signature: this.arrayBufferToBase64(
          assertion.response.signature
        ),
        userHandle: assertion.response.userHandle ? 
          this.arrayBufferToBase64(assertion.response.userHandle) : null
      },
      type: assertion.type
    };
    
    // Complete login
    const completeRes = await fetch('/api/auth/webauthn/login/complete/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        credential: assertionJSON
      })
    });
    
    return await completeRes.json();
  } catch (error) {
    console.error('WebAuthn login failed:', error);
    throw error;
  }
}
```

## Token Management

### Knox Token System

Ekko uses Django REST Knox for token management:

**Features:**
- Device-specific tokens
- 48-hour expiry (configurable)
- Secure token generation
- No token refresh needed

**Token Format:**
```
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

### Token Storage

**Best Practices:**
- Store in memory for web apps
- Use secure storage for mobile apps
- Never store in localStorage (XSS vulnerable)
- Clear on logout/browser close

**Example Storage (React):**
```javascript
// Use a secure state management solution
import { create } from 'zustand';

const useAuthStore = create((set) => ({
  token: null,
  setToken: (token) => set({ token }),
  clearToken: () => set({ token: null }),
}));
```

### Token Usage

```javascript
// API request with token
const response = await fetch('/api/alerts/', {
  headers: {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  }
});
```

## Security Features

### 1. Rate Limiting

**Email Verification Codes:**
- 5 requests per email per hour
- 5 attempts per code
- IP-based limiting for signup

**API Endpoints:**
- 100 requests per minute (authenticated)
- 20 requests per minute (unauthenticated)

### 2. Session Management

**Features:**
- Device tracking
- Session revocation
- Activity monitoring
- Concurrent session limits

**View Active Sessions:**
```javascript
const sessions = await fetch('/api/auth/sessions/', {
  headers: { 'Authorization': `Token ${token}` }
});
```

### 3. Account Recovery

**Recovery Options:**
1. Email verification code
2. Recovery codes (future)
3. Admin intervention

### 4. Security Headers

Required headers for production:
```
Content-Security-Policy: default-src 'self'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```

## Client Implementation

### React Example

```jsx
import { useState } from 'react';
import { WebAuthnHelper } from './webauthn-helper';

function LoginComponent() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const handleWebAuthnLogin = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const { knox_token, user } = await WebAuthnHelper.login(email);
      
      // Store token securely
      authStore.setToken(knox_token);
      authStore.setUser(user);
      
      // Redirect to dashboard
      navigate('/dashboard');
    } catch (err) {
      if (err.name === 'NotAllowedError') {
        setError('Authentication was cancelled or timed out');
      } else if (err.message.includes('credentials')) {
        // Fallback to email verification
        await handleEmailLogin();
      } else {
        setError('Authentication failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };
  
  const handleEmailLogin = async () => {
    // Implement email verification flow
  };
  
  return (
    <form onSubmit={(e) => { e.preventDefault(); handleWebAuthnLogin(); }}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Enter your email"
        required
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Authenticating...' : 'Login with Passkey'}
      </button>
      {error && <div className="error">{error}</div>}
    </form>
  );
}
```

### Mobile (React Native)

For React Native, use a WebAuthn polyfill or native modules:

```javascript
import { WebAuthn } from 'react-native-webauthn';

// Configure for your platform
WebAuthn.configure({
  rpId: 'your-domain.com',
  rpName: 'Ekko'
});

// Use similar flow as web
```

## Troubleshooting

### Common Issues

#### 1. "WebAuthn is not supported"

**Causes:**
- Old browser version
- Insecure context (not HTTPS)
- Disabled in browser settings

**Solution:**
```javascript
// Check WebAuthn support
if (!window.PublicKeyCredential) {
  // Fallback to email verification
  showEmailLoginOption();
}
```

#### 2. "User cancelled the operation"

**Causes:**
- User clicked cancel
- Timeout (60 seconds default)
- Biometric not recognized

**Solution:**
- Provide clear instructions
- Offer retry option
- Fallback to email verification

#### 3. "Invalid authenticator"

**Causes:**
- Authenticator not allowed
- Wrong user verification setting

**Solution:**
```javascript
// Allow both platform and cross-platform
options.publicKey.authenticatorSelection = {
  authenticatorAttachment: undefined, // Allow any
  userVerification: 'preferred'
};
```

### Debug Mode

Enable debug logging:

```javascript
// Client-side
if (process.env.NODE_ENV === 'development') {
  window.DEBUG_WEBAUTHN = true;
}

// Log all WebAuthn operations
if (window.DEBUG_WEBAUTHN) {
  console.log('WebAuthn options:', options);
  console.log('Credential created:', credential);
}
```

### Testing WebAuthn

**Local Development:**
1. Use Chrome DevTools → WebAuthn tab
2. Create virtual authenticators
3. Test different scenarios

**Example Test Setup:**
```javascript
// Cypress test
describe('WebAuthn Authentication', () => {
  beforeEach(() => {
    cy.visit('/login');
    // Mock WebAuthn API
    cy.window().then((win) => {
      win.navigator.credentials = {
        create: cy.stub().resolves(mockCredential),
        get: cy.stub().resolves(mockAssertion)
      };
    });
  });
  
  it('should login with passkey', () => {
    cy.get('[data-testid=email]').type('test@example.com');
    cy.get('[data-testid=login-button]').click();
    cy.url().should('include', '/dashboard');
  });
});
```

## Best Practices

### 1. Progressive Enhancement

Always provide fallback options:

```javascript
const AuthComponent = () => {
  const supportsWebAuthn = 'credentials' in navigator;
  
  return (
    <>
      {supportsWebAuthn ? (
        <PasskeyLogin />
      ) : (
        <EmailLogin />
      )}
    </>
  );
};
```

### 2. Error Handling

Provide clear, actionable error messages:

```javascript
const errorMessages = {
  'NotAllowedError': 'Please try again and approve the authentication prompt',
  'InvalidStateError': 'An authentication operation is already in progress',
  'NotSupportedError': 'Your device doesn\'t support passkeys. Please use email login.',
  'AbortError': 'Authentication was cancelled. Please try again.',
};
```

### 3. User Education

Help users understand passkeys:

```jsx
<InfoBox>
  <h3>What are passkeys?</h3>
  <p>Passkeys let you sign in with Face ID, Touch ID, or Windows Hello 
     instead of passwords. They're more secure and easier to use.</p>
  <LearnMoreLink href="/help/passkeys" />
</InfoBox>
```

### 4. Analytics

Track authentication metrics:

```javascript
// Track success/failure rates
analytics.track('auth.webauthn.attempt', { email });
analytics.track('auth.webauthn.success', { email, duration });
analytics.track('auth.webauthn.failure', { email, error: error.name });
```

## Migration Guide

### From Password-Based Auth

1. **Add WebAuthn to existing accounts:**
```javascript
// After password login
if (!user.hasPasskey) {
  showPasskeySetupPrompt();
}
```

2. **Gradual migration:**
- Phase 1: Optional passkeys
- Phase 2: Encourage passkey adoption
- Phase 3: Require passkeys for new users
- Phase 4: Deprecate passwords

### Security Considerations

1. **Always use HTTPS** - WebAuthn requires secure context
2. **Validate RP ID** - Must match your domain
3. **Store minimal data** - Only store credential ID and public key
4. **Monitor usage** - Track failed attempts and anomalies
5. **Plan for recovery** - Users may lose devices

## Additional Resources

- [WebAuthn Specification](https://www.w3.org/TR/webauthn/)
- [Passkeys.dev](https://passkeys.dev/)
- [FIDO Alliance](https://fidoalliance.org/)
- [Django Allauth MFA Docs](https://django-allauth.readthedocs.io/)