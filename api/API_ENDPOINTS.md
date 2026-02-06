# Ekko API Endpoints Documentation

This document provides detailed documentation for all API endpoints in the Ekko platform.

## Base URL

```
Development: http://localhost:8000/api/
Production: https://api.ekko.com/api/
```

## Authentication

All API requests (except authentication endpoints) require a Knox token in the Authorization header:

```
Authorization: Token <knox_token>
```

## Table of Contents

1. [Authentication Endpoints](#authentication-endpoints)
2. [Alert Template Endpoints](#alert-template-endpoints)
3. [Alert Endpoints](#alert-endpoints)
4. [Chain Endpoints](#chain-endpoints)
5. [Health Check Endpoints](#health-check-endpoints)
6. [Error Responses](#error-responses)

---

## Authentication Endpoints

### 1. Begin Signup

Start the signup process with an email address.

**Endpoint:** `POST /auth/signup/begin/`

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "message": "Verification code sent to email",
  "email": "user@example.com",
  "code_expires_at": "2025-01-01T10:10:00Z"
}
```

### 2. Verify Email

Verify the email with the 6-digit code.

**Endpoint:** `POST /auth/signup/verify-email/`

**Request Body:**
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**Response (200):**
```json
{
  "message": "Email verified successfully",
  "user_id": "uuid",
  "email": "user@example.com"
}
```

### 3. WebAuthn Registration Begin

Start WebAuthn registration process.

**Endpoint:** `POST /auth/webauthn/register/begin/`

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "publicKey": {
    "challenge": "base64-encoded-challenge",
    "rp": {
      "name": "Ekko",
      "id": "localhost"
    },
    "user": {
      "id": "base64-encoded-user-id",
      "name": "user@example.com",
      "displayName": "user@example.com"
    },
    "pubKeyCredParams": [...],
    "authenticatorSelection": {...},
    "timeout": 60000,
    "attestation": "none"
  }
}
```

### 4. WebAuthn Registration Complete

Complete WebAuthn registration with credential.

**Endpoint:** `POST /auth/webauthn/register/complete/`

**Request Body:**
```json
{
  "email": "user@example.com",
  "credential": {
    "id": "credential-id",
    "rawId": "base64-encoded-raw-id",
    "response": {
      "attestationObject": "base64-encoded",
      "clientDataJSON": "base64-encoded"
    },
    "type": "public-key"
  }
}
```

**Response (200):**
```json
{
  "message": "WebAuthn registration successful",
  "knox_token": "token-string",
  "expires": "2025-01-03T10:00:00Z",
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "display_name": null
  }
}
```

### 5. WebAuthn Login Begin

Start WebAuthn authentication.

**Endpoint:** `POST /auth/webauthn/login/begin/`

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "publicKey": {
    "challenge": "base64-encoded-challenge",
    "rpId": "localhost",
    "allowCredentials": [...],
    "timeout": 60000,
    "userVerification": "preferred"
  }
}
```

### 6. WebAuthn Login Complete

Complete WebAuthn authentication.

**Endpoint:** `POST /auth/webauthn/login/complete/`

**Request Body:**
```json
{
  "email": "user@example.com",
  "credential": {
    "id": "credential-id",
    "rawId": "base64-encoded-raw-id",
    "response": {
      "authenticatorData": "base64-encoded",
      "clientDataJSON": "base64-encoded",
      "signature": "base64-encoded"
    },
    "type": "public-key"
  }
}
```

**Response (200):**
```json
{
  "knox_token": "token-string",
  "expires": "2025-01-03T10:00:00Z",
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "display_name": "John Doe"
  }
}
```

### 7. Email Login

Fallback login method using email verification.

**Endpoint:** `POST /auth/login/email/`

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "message": "Verification code sent to email",
  "email": "user@example.com",
  "code_expires_at": "2025-01-01T10:10:00Z"
}
```

### 8. Verify Login Code

Verify the login code sent to email.

**Endpoint:** `POST /auth/login/verify/`

**Request Body:**
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**Response (200):**
```json
{
  "knox_token": "token-string",
  "expires": "2025-01-03T10:00:00Z",
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "display_name": "John Doe"
  }
}
```

### 9. Logout

Invalidate the current Knox token.

**Endpoint:** `POST /auth/logout/`

**Headers:**
```
Authorization: Token <knox_token>
```

**Response (204):** No content

---

## Alert Template Endpoints

### 1. List Alert Templates

Get a paginated list of alert templates.

**Endpoint:** `GET /alerts/templates/`

**Query Parameters:**
- `event_type` (optional): Filter by event type (e.g., ACCOUNT_EVENT)
- `sub_event` (optional): Filter by sub-event type
- `is_public` (optional): Filter public templates (true/false)
- `is_verified` (optional): Filter verified templates (true/false)
- `search` (optional): Search in name, description, and nl_template
- `ordering` (optional): Order by field (e.g., -created_at, usage_count)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 20)

**Response (200):**
```json
{
  "count": 50,
  "next": "http://localhost:8000/api/alerts/templates/?page=2",
  "previous": null,
  "results": [
    {
      "id": "template-uuid",
      "name": "Balance Threshold Alert",
      "description": "Alert when wallet balance exceeds threshold",
      "nl_template": "Alert me when {{wallet}} balance goes above {{threshold}} {{token}}",
      "spec_blueprint": {
        "event_type": "BALANCE_THRESHOLD",
        "conditions": "balance > {{threshold}}"
      },
      "variables": [
        {"name": "wallet", "type": "address"},
        {"name": "threshold", "type": "number"},
        {"name": "token", "type": "string"}
      ],
      "event_type": "ACCOUNT_EVENT",
      "sub_event": "BALANCE_THRESHOLD",
      "version": 1,
      "usage_count": 42,
      "is_public": true,
      "is_verified": true,
      "created_by": {
        "id": "user-uuid",
        "email": "creator@example.com",
        "display_name": "Template Creator"
      },
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

### 2. Create Alert Template

Create a new alert template.

**Endpoint:** `POST /alerts/templates/`

**Request Body:**
```json
{
  "name": "Token Transfer Alert",
  "description": "Alert on token transfers",
  "nl_template": "Alert me when {{token}} is transferred from {{wallet}}",
  "spec_blueprint": {
    "event_type": "TOKEN_TRANSFER",
    "conditions": {
      "from_address": "{{wallet}}",
      "token": "{{token}}"
    }
  },
  "variables": [
    {"name": "wallet", "type": "address", "required": true},
    {"name": "token", "type": "string", "required": true}
  ],
  "event_type": "ASSET_EVENT",
  "sub_event": "TOKEN_TRANSFER",
  "is_public": false
}
```

**Response (201):**
```json
{
  "id": "new-template-uuid",
  "name": "Token Transfer Alert",
  // ... full template object
}
```

### 3. Get Alert Template

Get a specific alert template by ID.

**Endpoint:** `GET /alerts/templates/{template_id}/`

**Response (200):** Full template object

### 4. Update Alert Template

Update an existing alert template.

**Endpoint:** `PUT /alerts/templates/{template_id}/`

**Request Body:** Same as create, all fields optional

**Response (200):** Updated template object

### 5. Delete Alert Template

Delete an alert template.

**Endpoint:** `DELETE /alerts/templates/{template_id}/`

**Response (204):** No content

### 6. Get Popular Templates

Get the most popular public templates.

**Endpoint:** `GET /alerts/templates/popular/`

**Response (200):**
```json
[
  {
    "id": "template-uuid",
    "name": "Popular Template",
    "usage_count": 1000,
    // ... template fields
  }
]
```

### 7. Get Templates by Event Type

Get templates filtered by a specific event type.

**Endpoint:** `GET /alerts/templates/by_event_type/`

**Query Parameters:**
- `event_type` (required): Event type to filter by

**Response (200):** Array of templates

### 8. Instantiate Template

Create an alert from a template.

**Endpoint:** `POST /alerts/templates/{template_id}/instantiate/`

**Request Body:**
```json
{
  "params": {
    "wallet": "0x123...",
    "threshold": 100,
    "token": "AVAX"
  },
  "name": "My Custom Alert Name"  // optional
}
```

**Response (201):**
```json
{
  "id": "alert-uuid",
  "name": "My Custom Alert Name",
  "nl_description": "Alert me when 0x123... balance goes above 100 AVAX",
  "enabled": true,
  // ... full alert object
}
```

---

## Alert Endpoints

### 1. List Alerts

Get a paginated list of user's alerts.

**Endpoint:** `GET /alerts/`

**Query Parameters:**
- `enabled` (optional): Filter by enabled status (true/false)
- `version` (optional): Filter by version number
- `event_type` (optional): Filter by event type
- `sub_event` (optional): Filter by sub-event type
- `template` (optional): Filter by template ID
- `chain` (optional): Filter by blockchain (e.g., ethereum, bitcoin)
- `latest_only` (optional): Show only latest versions (default: true)
- `search` (optional): Search in name and nl_description
- `ordering` (optional): Order by field (e.g., -created_at, name)
- `page` (optional): Page number
- `page_size` (optional): Items per page

**Response (200):**
```json
{
  "count": 25,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "alert-uuid",
      "name": "AVAX Balance Alert",
      "nl_description": "Alert me when my AVAX balance goes above 10",
      "enabled": true,
      "version": 1,
      "event_type": "ACCOUNT_EVENT",
      "sub_event": "BALANCE_THRESHOLD",
      "template": {
        "id": "template-uuid",
        "name": "Balance Threshold Template"
      },
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

### 2. Create Alert

Create a new alert directly (without template).

**Endpoint:** `POST /alerts/`

**Request Body:**
```json
{
  "name": "ETH Gas Price Alert",
  "nl_description": "Alert me when ETH gas price goes below 50 gwei",
  "event_type": "PROTOCOL_EVENT",
  "sub_event": "GAS_PRICE_THRESHOLD"
}
```

**Response (201):** Created alert object

**Note:** This will enqueue NLP parsing (with NATS progress events) to generate the alert specification.

### 3. Get Alert Details

Get full details of a specific alert.

**Endpoint:** `GET /alerts/{alert_id}/`

**Response (200):**
```json
{
  "id": "alert-uuid",
  "name": "AVAX Balance Alert",
  "nl_description": "Alert me when my AVAX balance goes above 10",
  "spec": {
    "version": "1.0",
    "event_type": "BALANCE_THRESHOLD",
    "conditions": {
      "balance": "> 10",
      "token": "AVAX"
    },
    "scope": {
      "chains": ["avalanche"],
      "addresses": ["0x123..."]
    }
  },
  "enabled": true,
  "version": 1,
  "event_type": "ACCOUNT_EVENT",
  "sub_event": "BALANCE_THRESHOLD",
  "template": null,
  "user": {
    "id": "user-uuid",
    "email": "user@example.com"
  },
  "jobs": [],
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

### 4. Update Alert

Update an existing alert.

**Endpoint:** `PUT /alerts/{alert_id}/`

**Request Body:**
```json
{
  "name": "Updated Alert Name",
  "enabled": false
}
```

**Response (200):** Updated alert object

**Note:** Updates create a new version and trigger NATS message for reprocessing.

### 5. Delete Alert

Delete an alert.

**Endpoint:** `DELETE /alerts/{alert_id}/`

**Response (204):** No content

### 6. Enable Alert

Enable a disabled alert.

**Endpoint:** `POST /alerts/{alert_id}/enable/`

**Response (200):**
```json
{
  "message": "Alert enabled successfully"
}
```

### 7. Disable Alert

Disable an enabled alert.

**Endpoint:** `POST /alerts/{alert_id}/disable/`

**Response (200):**
```json
{
  "message": "Alert disabled successfully"
}
```

### 8. Get Alert Versions

Get all versions of an alert.

**Endpoint:** `GET /alerts/{alert_id}/versions/`

**Response (200):**
```json
{
  "count": 3,
  "results": [
    {
      "id": "alert-uuid",
      "version": 3,
      "created_at": "2025-01-03T00:00:00Z",
      // ... alert fields
    },
    {
      "id": "alert-uuid",
      "version": 2,
      "created_at": "2025-01-02T00:00:00Z",
      // ... alert fields
    }
  ]
}
```

### 9. Get Specific Version

Get a specific version of an alert.

**Endpoint:** `GET /alerts/{alert_id}/version/?version=2`

**Query Parameters:**
- `version` (required): Version number

**Response (200):** Alert object for specified version

### 10. Get Alert Changelog

Get the change history for an alert.

**Endpoint:** `GET /alerts/{alert_id}/changelog/`

**Response (200):**
```json
{
  "count": 5,
  "results": [
    {
      "id": "changelog-uuid",
      "alert": "alert-uuid",
      "from_version": 1,
      "to_version": 2,
      "change_type": "updated",
      "changed_fields": ["name", "spec"],
      "old_values": {
        "name": "Old Name",
        "spec": {...}
      },
      "new_values": {
        "name": "New Name",
        "spec": {...}
      },
      "changed_by": {
        "id": "user-uuid",
        "email": "user@example.com"
      },
      "created_at": "2025-01-02T00:00:00Z"
    }
  ]
}
```

### 11. Get Alert Jobs

Get jobs associated with an alert.

**Endpoint:** `GET /alerts/{alert_id}/jobs/`

**Response (200):**
```json
{
  "count": 10,
  "results": [
    {
      "id": "job-uuid",
      "alert": "alert-uuid",
      "job_type": "process_spec",
      "payload": {...},
      "status": "completed",
      "priority": "normal",
      "attempts": 1,
      "max_attempts": 3,
      "result": {...},
      "error": null,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:01:00Z",
      "completed_at": "2025-01-01T00:01:00Z"
    }
  ]
}
```

### 12. Get Alert Executions

Get execution history for an alert.

**Endpoint:** `GET /alerts/{alert_id}/executions/`

**Response (200):**
```json
{
  "count": 100,
  "results": [
    {
      "id": "execution-uuid",
      "alert": "alert-uuid",
      "alert_version": 1,
      "trigger_type": "blockchain_event",
      "trigger_data": {
        "transaction_hash": "0xabc...",
        "block_number": 12345678
      },
      "conditions_met": true,
      "notifications_sent": 2,
      "execution_time_ms": 45,
      "error": null,
      "started_at": "2025-01-01T10:00:00Z",
      "completed_at": "2025-01-01T10:00:00.045Z"
    }
  ]
}
```

---

## Chain Endpoints

### 1. List Chains

Get a list of supported blockchains.

**Endpoint:** `GET /chains/`

**Query Parameters:**
- `search` (optional): Search in name and display_name
- `ordering` (optional): Order by field

**Response (200):**
```json
{
  "count": 10,
  "results": [
    {
      "id": "chain-uuid",
      "name": "ethereum",
      "display_name": "Ethereum",
      "chain_id": 1,
      "native_token": "ETH"
    },
    {
      "id": "chain-uuid",
      "name": "bitcoin",
      "display_name": "Bitcoin",
      "chain_id": null,
      "native_token": "BTC"
    }
  ]
}
```

### 2. Get Chain Details

Get details of a specific chain.

**Endpoint:** `GET /chains/{chain_id}/`

**Response (200):** Chain object

### 3. Get Chain Sub-chains

Get sub-chains (e.g., testnets) for a chain.

**Endpoint:** `GET /chains/{chain_id}/sub_chains/`

**Response (200):**
```json
[
  {
    "id": "subchain-uuid",
    "name": "sepolia",
    "display_name": "Sepolia Testnet",
    "network_id": 11155111,
    "is_testnet": true
  }
]
```

---

## Health Check Endpoints

### 1. Basic Health Check

Simple health check endpoint.

**Endpoint:** `GET /health/`

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T10:00:00Z"
}
```

### 2. Detailed Health Check

Detailed health check with dependency status.

**Endpoint:** `GET /health/detailed/`

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T10:00:00Z",
  "dependencies": {
    "database": {
      "status": "healthy",
      "response_time_ms": 5
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 2
    },
    "nats": {
      "status": "healthy",
      "response_time_ms": 3,
      "connected": true
    }
  },
  "version": "1.0.0"
}
```

---

## Error Responses

All endpoints use consistent error response format:

### 400 Bad Request
```json
{
  "error": "Validation error",
  "details": {
    "field_name": ["Error message"]
  }
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

### 429 Too Many Requests
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 30
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "message": "An unexpected error occurred"
}
```

---

## Rate Limiting

API endpoints are rate limited to prevent abuse:

- **Authentication endpoints**: 5 requests per minute per IP
- **Alert creation**: 20 requests per minute per user
- **General API calls**: 100 requests per minute per user

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Pagination

List endpoints support pagination with the following parameters:

- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

Paginated responses include:
- `count`: Total number of items
- `next`: URL for next page (null if last page)
- `previous`: URL for previous page (null if first page)
- `results`: Array of items

---

## Filtering and Searching

Most list endpoints support:

- **Filtering**: Use query parameters to filter results
- **Searching**: Use `search` parameter for text search
- **Ordering**: Use `ordering` parameter with field name
  - Prefix with `-` for descending order (e.g., `-created_at`)

---

## Webhook Notifications

When alerts are triggered, webhooks can be configured to receive notifications:

**Webhook Payload:**
```json
{
  "event": "alert.triggered",
  "alert": {
    "id": "alert-uuid",
    "name": "Alert Name"
  },
  "trigger": {
    "type": "blockchain_event",
    "data": {...}
  },
  "timestamp": "2025-01-01T10:00:00Z"
}
```

Webhook configuration is managed through the Django Admin interface.
