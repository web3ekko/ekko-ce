# 🔌 Ekko CE - API Reference

## 🎯 **BASE URL**
```
http://localhost:8000
```

## 🔐 **AUTHENTICATION**

### **Login**
```http
POST /token
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

### **Using JWT Token**
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

---

## 💰 **WALLETS API**

### **List Wallets**
```http
GET /wallets
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": "01234567-89ab-cdef-0123-456789abcdef",
    "name": "My Main Wallet",
    "address": "0x1234567890abcdef1234567890abcdef12345678",
    "network": "avalanche",
    "created_at": "2025-06-20T10:00:00Z",
    "updated_at": "2025-06-20T10:00:00Z"
  }
]
```

### **Create Wallet**
```http
POST /wallets
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Trading Wallet",
  "address": "0xabcdef1234567890abcdef1234567890abcdef12",
  "network": "avalanche"
}
```

**Response:**
```json
{
  "id": "01234567-89ab-cdef-0123-456789abcdef",
  "name": "Trading Wallet",
  "address": "0xabcdef1234567890abcdef1234567890abcdef12",
  "network": "avalanche",
  "created_at": "2025-06-20T10:00:00Z",
  "updated_at": "2025-06-20T10:00:00Z"
}
```

### **Get Wallet**
```http
GET /wallets/{wallet_id}
Authorization: Bearer {token}
```

### **Update Wallet**
```http
PUT /wallets/{wallet_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Updated Wallet Name"
}
```

### **Delete Wallet**
```http
DELETE /wallets/{wallet_id}
Authorization: Bearer {token}
```

---

## 🖥️ **NODES API**

### **List Nodes**
```http
GET /nodes
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": "01234567-89ab-cdef-0123-456789abcdef",
    "name": "Avalanche Mainnet",
    "rpc_url": "https://api.avax.network/ext/bc/C/rpc",
    "network": "avalanche",
    "subnet": "mainnet",
    "vmtype": "evm",
    "is_active": true,
    "created_at": "2025-06-20T10:00:00Z"
  }
]
```

### **Create Node**
```http
POST /nodes
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Custom Node",
  "rpc_url": "https://rpc.example.com",
  "network": "avalanche",
  "subnet": "mainnet",
  "vmtype": "evm"
}
```

### **Validation Rules:**
- Each `network + subnet + vmtype` combination must be unique
- `rpc_url` must be a valid HTTP/HTTPS URL
- `network` must be a valid blockchain network
- `vmtype` must be one of: `evm`, `wasm`, `substrate`

---

## 🚨 **ALERTS API**

### **List Alerts**
```http
GET /alerts
Authorization: Bearer {token}
```

**Response:**
```json
[
  {
    "id": "01234567-89ab-cdef-0123-456789abcdef",
    "name": "Low Balance Alert",
    "description": "Alert when wallet balance drops below 10 AVAX",
    "natural_language_query": "Alert me when my wallet balance is below 10 AVAX",
    "polars_dsl": "wallet_balances.filter(pl.col('balance') < 10.0)",
    "parameters": {
      "wallet_address": "0x1234...",
      "threshold": 10.0,
      "token": "AVAX"
    },
    "is_active": true,
    "created_at": "2025-06-20T10:00:00Z"
  }
]
```

### **Create Alert**
```http
POST /alerts
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "High Gas Alert",
  "description": "Alert when gas prices are high",
  "natural_language_query": "Alert me when gas prices exceed 50 gwei"
}
```

### **DSPy Alert Inference**
```http
POST /alerts/infer
Authorization: Bearer {token}
Content-Type: application/json

{
  "natural_language_query": "Alert me when my wallet balance drops below 5 AVAX",
  "context": {
    "available_wallets": ["0x1234..."],
    "available_tokens": ["AVAX", "USDC"]
  }
}
```

**Response:**
```json
{
  "success": true,
  "inferred_parameters": {
    "alert_type": "wallet_balance_threshold",
    "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
    "threshold": 5.0,
    "token_symbol": "AVAX",
    "comparison_operator": "less_than"
  },
  "confidence_score": 0.95,
  "template_used": "wallet_balance_threshold"
}
```

### **Generate DSL Preview**
```http
POST /alerts/preview-dsl
Authorization: Bearer {token}
Content-Type: application/json

{
  "natural_language_query": "Alert me when my wallet balance drops below 5 AVAX",
  "inferred_parameters": {
    "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
    "threshold": 5.0,
    "token_symbol": "AVAX"
  }
}
```

**Response:**
```json
{
  "success": true,
  "polars_dsl": "let target_wallet = wallet_balances.filter(pl.col('address') == '0x1234567890abcdef1234567890abcdef12345678').filter(pl.col('token_symbol') == 'AVAX').with_columns([(pl.col('balance') < 5.0).alias('below_threshold'), pl.col('balance').alias('current_value')]); target_wallet",
  "data_sources": ["wallet_balances"],
  "output_mapping": {
    "result_column": "below_threshold",
    "value_column": "current_value",
    "result_type": "boolean",
    "value_type": "float"
  },
  "explanation": "This query checks if the wallet balance is below the threshold of 5.0 AVAX"
}
```

---

## ⚡ **ALERT EXECUTION API**

### **Executor Statistics**
```http
GET /alerts/executor/stats
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "active_executions": 2,
    "max_concurrent_executions": 10,
    "worker_id": "worker-cdd100b8",
    "connected": true,
    "running": true
  }
}
```

### **Test Execution**
```http
POST /alerts/test-execution
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "message": "Test execution request sent to processing queue",
  "test_request": {
    "alert_id": "test_wallet_balance",
    "polars_dsl": "# Test wallet balance check...",
    "data_sources": ["wallet_balances"],
    "output_mapping": {
      "result_column": "below_threshold",
      "value_column": "current_value"
    }
  }
}
```

### **Execute Custom DSL**
```http
POST /alerts/execute-dsl
Authorization: Bearer {token}
Content-Type: application/json

{
  "alert_id": "custom_query",
  "polars_dsl": "wallet_balances.filter(pl.col('balance') > 100.0)",
  "data_sources": ["wallet_balances"],
  "output_mapping": {
    "result_column": "result",
    "value_column": "value"
  },
  "timeout_seconds": 30
}
```

**Response:**
```json
{
  "success": true,
  "execution_id": "e8283bf8-67b3-437c-9771-7ce8d69f3a26",
  "message": "Alert execution request sent to processing queue"
}
```

---

## 💳 **TRANSACTIONS API**

### **List Transactions**
```http
GET /api/transactions?limit=50&offset=0&network=avalanche
Authorization: Bearer {token}
```

**Query Parameters:**
- `limit` (optional): Number of results (default: 50, max: 1000)
- `offset` (optional): Pagination offset (default: 0)
- `network` (optional): Filter by network
- `wallet_address` (optional): Filter by wallet address
- `from_date` (optional): Start date (ISO format)
- `to_date` (optional): End date (ISO format)

**Response:**
```json
{
  "transactions": [
    {
      "hash": "0xabc123def456...",
      "from": "0x1234567890abcdef1234567890abcdef12345678",
      "to": "0xabcdef1234567890abcdef1234567890abcdef12",
      "value": "12.5",
      "token_symbol": "AVAX",
      "timestamp": "2025-06-20T08:00:00Z",
      "network": "avalanche",
      "subnet": "mainnet",
      "gas_price": "25.0",
      "gas_used": "21000",
      "status": "success"
    }
  ],
  "total": 1250,
  "limit": 50,
  "offset": 0
}
```

### **Get Transaction**
```http
GET /api/transactions/{transaction_hash}
Authorization: Bearer {token}
```

---

## ⚙️ **SETTINGS API**

### **Get Notification Settings**
```http
GET /api/settings/notifications
Authorization: Bearer {token}
```

**Response:**
```json
{
  "email": {
    "enabled": true,
    "destinations": [
      {
        "address": "user@example.com",
        "enabled": true
      }
    ]
  },
  "telegram": {
    "enabled": false,
    "destinations": []
  },
  "discord": {
    "enabled": true,
    "destinations": [
      {
        "webhook_url": "https://discord.com/api/webhooks/...",
        "enabled": true
      }
    ]
  }
}
```

### **Update Notification Settings**
```http
PUT /api/settings/notifications
Authorization: Bearer {token}
Content-Type: application/json

{
  "email": {
    "enabled": true,
    "destinations": [
      {
        "address": "newemail@example.com",
        "enabled": true
      }
    ]
  }
}
```

---

## 🏠 **SYSTEM API**

### **Health Check**
```http
GET /
```

**Response:**
```json
{
  "status": "healthy",
  "service": "ekko-ce-api",
  "version": "1.0.0",
  "timestamp": "2025-06-20T15:30:00Z"
}
```

### **Database Status**
```http
GET /database/status
Authorization: Bearer {token}
```

**Response:**
```json
{
  "status": "connected",
  "database_type": "duckdb",
  "tables": ["wallets", "nodes", "alerts"],
  "nats_connected": true,
  "last_health_check": "2025-06-20T15:30:00Z"
}
```

---

## 🚨 **ERROR RESPONSES**

### **Standard Error Format:**
```json
{
  "detail": "Error message description",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-06-20T15:30:00Z"
}
```

### **Common HTTP Status Codes:**
- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (duplicate resource)
- `422` - Unprocessable Entity (validation error)
- `500` - Internal Server Error

---

## 📊 **RATE LIMITS**

- **General API**: 1000 requests/hour per user
- **Alert Execution**: 100 requests/hour per user
- **DSPy Inference**: 50 requests/hour per user

---

## 🔧 **DEVELOPMENT TOOLS**

### **Interactive API Documentation:**
```
http://localhost:8000/docs
```

### **OpenAPI Schema:**
```
http://localhost:8000/openapi.json
```

This API reference provides comprehensive documentation for all available endpoints in the Ekko CE platform. 🚀
