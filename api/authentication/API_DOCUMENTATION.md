# Ekko API Authentication Documentation
## Passwordless Authentication Endpoints

This document provides complete API documentation for the Ekko passwordless authentication system.

## 🔑 Authentication Flow

```
Signup:  POST /api/auth/signup/begin/ → Email Verification → POST /api/auth/signup/complete/
Login:   POST /api/auth/login/ → Passkey/Magic Link → Success
Recovery: POST /api/auth/recovery/ → Email Link → New Passkey Setup
```

## 📋 Base URL
```
Production: https://api.ekko.dev
Development: http://localhost:8000
```

## 🔐 Authentication Endpoints

### 1. Begin Signup
Start the passwordless signup process.

**Endpoint:** `POST /api/auth/signup/begin/`

**Request Body:**
```json
{
  "email": "user@example.com",
  "device_info": {
    "webauthn_supported": true,
    "biometric_supported": true,
    "user_agent": "Mozilla/5.0...",
    "device_type": "web"
  }
}
```

**Response (200 OK):**
```json
{
  "email": "user@example.com",
  "auth_options": [
    {
      "method": "passkey",
      "name": "Sign up with passkey",
      "primary": true,
      "description": "Use Touch ID/Face ID to create a passkey"
    },
    {
      "method": "email",
      "name": "Email verification",
      "primary": false,
      "description": "We'll send a verification link to your email"
    }
  ],
  "recommended_method": "passkey",
  "message": "Verification email sent. Please check your inbox.",
  "next_step": "verify_email"
}
```

**Error Responses:**
```json
// 400 Bad Request - Email already exists
{
  "error": "Email already registered"
}

// 400 Bad Request - Invalid email
{
  "email": ["Enter a valid email address."]
}
```

### 2. Complete Signup
Complete signup after email verification and optional passkey creation.

**Endpoint:** `POST /api/auth/signup/complete/`

**Request Body:**
```json
{
  "token": "email-verification-token-from-email",
  "first_name": "John",
  "last_name": "Doe",
  "device_info": {
    "webauthn_supported": true,
    "device_type": "web"
  },
  "credential_data": {
    // WebAuthn credential data (optional)
    "id": "credential-id",
    "rawId": "raw-credential-id",
    "response": {
      "attestationObject": "...",
      "clientDataJSON": "..."
    },
    "type": "public-key"
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Account created successfully!",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "recovery_codes": [
    "ABCD-1234",
    "EFGH-5678",
    // ... 8 more codes
  ],
  "next_steps": [
    "save_recovery_codes",
    "setup_passkey"
  ]
}
```

### 3. Passwordless Login
Initiate login with automatic method detection.

**Endpoint:** `POST /api/auth/login/`

**Request Body:**
```json
{
  "email": "user@example.com",
  "auth_method": "auto", // "auto", "passkey", "email_magic_link"
  "device_info": {
    "webauthn_supported": true,
    "device_type": "web"
  }
}
```

**Response - Passkey Available (200 OK):**
```json
{
  "email": "user@example.com",
  "available_methods": [
    {
      "method": "passkey",
      "name": "Use Touch ID/Face ID",
      "primary": true,
      "description": "Sign in with your passkey"
    },
    {
      "method": "email_magic_link",
      "name": "Send magic link",
      "primary": false,
      "description": "We'll send a sign-in link to your email"
    }
  ],
  "recommended_method": "passkey",
  "has_2fa": false
}
```

**Response - Magic Link Sent (200 OK):**
```json
{
  "method": "email_magic_link",
  "message": "Sign-in link sent to your email",
  "email": "user@example.com",
  "expires_in": 900
}
```

### 4. Verify Magic Link
Authenticate using email magic link.

**Endpoint:** `POST /api/auth/login/magic-link/`

**Request Body:**
```json
{
  "token": "magic-link-token-from-email",
  "device_info": {
    "webauthn_supported": true,
    "device_type": "web"
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "auth_method": "email_magic_link",
  "device_trusted": false,
  "message": "Successfully signed in"
}
```

**Response - 2FA Required (200 OK):**
```json
{
  "success": true,
  "requires_2fa": true,
  "available_2fa_methods": ["totp"],
  "session_token": "2fa-session-token",
  "message": "Please complete 2FA verification"
}
```

### 5. Account Recovery
Initiate account recovery for lost passkey.

**Endpoint:** `POST /api/auth/recovery/`

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "message": "Recovery instructions have been sent to your email"
}
```

### 6. Logout
Sign out the current user.

**Endpoint:** `POST /api/auth/logout/`

**Headers:**
```
Authorization: Bearer <session-token>
```

**Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

## 🔧 WebAuthn Integration

### Passkey Registration Options
**Endpoint:** `POST /accounts/webauthn/signup/begin/`

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "rp": {
    "id": "your-domain.com",
    "name": "Ekko"
  },
  "user": {
    "id": "base64-user-id",
    "name": "user@example.com",
    "displayName": "John Doe"
  },
  "challenge": "base64-challenge",
  "pubKeyCredParams": [
    {
      "type": "public-key",
      "alg": -7
    }
  ],
  "timeout": 60000,
  "attestation": "none",
  "authenticatorSelection": {
    "authenticatorAttachment": "platform",
    "userVerification": "required"
  }
}
```

### Passkey Authentication Options
**Endpoint:** `POST /accounts/webauthn/login/begin/`

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "challenge": "base64-challenge",
  "timeout": 60000,
  "rpId": "your-domain.com",
  "allowCredentials": [
    {
      "type": "public-key",
      "id": "base64-credential-id"
    }
  ],
  "userVerification": "required"
}
```

## 📱 Device Management

### List User Devices
**Endpoint:** `GET /api/auth/devices/`

**Headers:**
```
Authorization: Bearer <session-token>
```

**Response (200 OK):**
```json
{
  "devices": [
    {
      "id": "uuid",
      "device_name": "iPhone 15 (Safari)",
      "device_type": "ios",
      "supports_passkey": true,
      "is_trusted": true,
      "last_used": "2024-01-15T10:30:00Z",
      "created_at": "2024-01-01T09:00:00Z"
    }
  ]
}
```

### Trust Device
**Endpoint:** `POST /api/auth/devices/{device_id}/trust/`

**Headers:**
```
Authorization: Bearer <session-token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Device trusted for 90 days"
}
```

## 🔐 2FA Management

### Setup TOTP
**Endpoint:** `POST /api/auth/totp/setup/`

**Headers:**
```
Authorization: Bearer <session-token>
```

**Response (200 OK):**
```json
{
  "qr_code": "data:image/png;base64,...",
  "manual_key": "JBSWY3DPEHPK3PXP",
  "backup_codes": [
    "12345678",
    "87654321"
  ]
}
```

### Verify TOTP
**Endpoint:** `POST /api/auth/totp/verify/`

**Request Body:**
```json
{
  "totp_code": "123456",
  "session_token": "2fa-session-token"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "2FA verification successful"
}
```

## 🚨 Error Handling

### Standard Error Format
```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {
    "field": ["Field-specific error message"]
  }
}
```

### Common Error Codes
- `INVALID_EMAIL` - Email format is invalid
- `EMAIL_EXISTS` - Email already registered
- `USER_NOT_FOUND` - User account not found
- `INVALID_TOKEN` - Token is invalid or expired
- `RATE_LIMITED` - Too many requests
- `WEBAUTHN_FAILED` - WebAuthn operation failed
- `2FA_REQUIRED` - 2FA verification required
- `DEVICE_NOT_TRUSTED` - Device requires trust verification

## 🔒 Security Headers

All API requests should include:
```
Content-Type: application/json
X-Requested-With: XMLHttpRequest
```

Authenticated requests require:
```
Authorization: Bearer <session-token>
```

## 📊 Rate Limiting

- **Authentication attempts**: 5 per email per 15 minutes
- **Magic link requests**: 3 per email per 5 minutes
- **API requests**: 100 per IP per minute

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## 🌐 CORS Configuration

Allowed origins for web clients:
- `https://your-domain.com`
- `http://localhost:3000` (development)

## 📱 Deep Link URLs

### Magic Link Format
```
Web:     https://your-domain.com/auth?token=<token>
iOS:     ekko://auth?token=<token>
Android: ekko://auth?token=<token>
```

### Recovery Link Format
```
Web:     https://your-domain.com/recovery?token=<token>
iOS:     ekko://recovery?token=<token>
Android: ekko://recovery?token=<token>
```
