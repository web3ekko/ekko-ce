# 📡 Ekko CE - NATS Subjects & Message Schemas

## 🎯 **OVERVIEW**

This document defines all NATS JetStream subjects, message schemas, and communication patterns used in the Ekko CE platform.

## 🏗️ **SUBJECT NAMING CONVENTION**

```
{domain}.{action}.{network}.{subnet}
```

**Examples:**
- `tx.created.avalanche.mainnet`
- `wallet.updated`
- `alert.execute`
- `system.startup`

---

## 📊 **SUBJECT CATEGORIES**

### 🔄 **1. TRANSACTION SUBJECTS**

#### **Published by:** Pipeline Service
#### **Consumed by:** Transactions Writer, API Background Processor

```
tx.created.{network}.{subnet}     # New transaction detected
tx.confirmed.{network}.{subnet}   # Transaction confirmed
tx.failed.{network}.{subnet}      # Transaction failed
```

**Message Schema:**
```json
{
  "hash": "0xabc123def456789...",
  "from": "0x1234567890abcdef1234567890abcdef12345678",
  "to": "0xabcdef1234567890abcdef1234567890abcdef12",
  "value": "12.5",
  "token_symbol": "AVAX",
  "network": "avalanche",
  "subnet": "mainnet",
  "block_number": 12345678,
  "block_hash": "0xblock123...",
  "transaction_index": 0,
  "gas_price": "25.0",
  "gas_limit": "21000",
  "gas_used": "21000",
  "status": "success",
  "timestamp": "2025-06-20T08:00:00Z",
  "details": {
    "transaction_type": "transfer",
    "contract_address": null,
    "input_data": "0x",
    "logs": []
  },
  "metadata": {
    "fetcher_id": "fetcher-avalanche-mainnet",
    "processed_at": "2025-06-20T08:00:01Z",
    "source_node": "https://api.avax.network/ext/bc/C/rpc"
  }
}
```

---

### 🏦 **2. WALLET SUBJECTS**

#### **Published by:** API Service
#### **Consumed by:** Dashboard, Pipeline Service

```
wallet.created                   # New wallet added
wallet.updated                   # Wallet information updated
wallet.deleted                   # Wallet removed
wallet.balance.updated           # Balance change detected
```

**wallet.created Schema:**
```json
{
  "event_id": "uuid",
  "wallet_id": "01234567-89ab-cdef-0123-456789abcdef",
  "name": "My Trading Wallet",
  "address": "0x1234567890abcdef1234567890abcdef12345678",
  "network": "avalanche",
  "created_by": "user_id",
  "created_at": "2025-06-20T10:00:00Z",
  "metadata": {
    "source": "api",
    "user_agent": "dashboard/1.0.0"
  }
}
```

**wallet.balance.updated Schema:**
```json
{
  "wallet_id": "01234567-89ab-cdef-0123-456789abcdef",
  "address": "0x1234567890abcdef1234567890abcdef12345678",
  "network": "avalanche",
  "balances": [
    {
      "token_symbol": "AVAX",
      "balance": "15.5",
      "usd_value": "697.50",
      "previous_balance": "18.2",
      "change": "-2.7",
      "change_percent": "-14.84"
    }
  ],
  "timestamp": "2025-06-20T08:00:00Z",
  "block_number": 12345678
}
```

---

### 🖥️ **3. NODE SUBJECTS**

#### **Published by:** API Service
#### **Consumed by:** Pipeline Service

```
node.created                     # New node configuration
node.updated                     # Node settings changed
node.deleted                     # Node removed
node.health.updated              # Node health status change
```

**node.created Schema:**
```json
{
  "event_id": "uuid",
  "node_id": "01234567-89ab-cdef-0123-456789abcdef",
  "name": "Avalanche Mainnet RPC",
  "rpc_url": "https://api.avax.network/ext/bc/C/rpc",
  "network": "avalanche",
  "subnet": "mainnet",
  "vmtype": "evm",
  "is_active": true,
  "created_at": "2025-06-20T10:00:00Z",
  "metadata": {
    "created_by": "user_id",
    "source": "api"
  }
}
```

**node.health.updated Schema:**
```json
{
  "node_id": "01234567-89ab-cdef-0123-456789abcdef",
  "rpc_url": "https://api.avax.network/ext/bc/C/rpc",
  "network": "avalanche",
  "subnet": "mainnet",
  "health_status": "healthy",
  "response_time_ms": 150,
  "last_block": 12345678,
  "sync_status": "synced",
  "error_message": null,
  "checked_at": "2025-06-20T08:00:00Z",
  "metadata": {
    "checker_id": "health-monitor-1",
    "consecutive_failures": 0
  }
}
```

---

### 🚨 **4. ALERT SUBJECTS**

#### **Published by:** API Service, Alert Executor
#### **Consumed by:** Alert Executor, API Service, Dashboard

```
alert.created                    # New alert configured
alert.updated                    # Alert settings changed
alert.deleted                    # Alert removed
alert.execute                    # Execute alert query
alert.result                     # Alert execution result
alert.error                      # Alert execution error
alert.triggered                  # Alert condition met
```

**alert.execute Schema:**
```json
{
  "execution_id": "e8283bf8-67b3-437c-9771-7ce8d69f3a26",
  "alert_id": "01234567-89ab-cdef-0123-456789abcdef",
  "polars_dsl": "wallet_balances.filter(pl.col('address') == '0x1234...').filter(pl.col('balance') < 10.0)",
  "data_sources": ["wallet_balances", "price_feeds"],
  "output_mapping": {
    "result_column": "below_threshold",
    "value_column": "current_value",
    "result_type": "boolean",
    "value_type": "float"
  },
  "parameters_used": {
    "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
    "threshold": 10.0,
    "token_symbol": "AVAX"
  },
  "timeout_seconds": 30,
  "priority": "Normal",
  "requested_at": "2025-06-20T08:00:00Z",
  "metadata": {
    "requested_by": "user_id",
    "source": "scheduled_check"
  }
}
```

**alert.result Schema:**
```json
{
  "execution_id": "e8283bf8-67b3-437c-9771-7ce8d69f3a26",
  "alert_id": "01234567-89ab-cdef-0123-456789abcdef",
  "result": false,
  "value": "15.5",
  "metadata": {
    "execution_time_ms": 42,
    "rows_processed": 1,
    "data_sources_used": ["wallet_balances"],
    "worker_id": "worker-cdd100b8",
    "cache_hit": false,
    "validation_warnings": []
  },
  "completed_at": "2025-06-20T08:00:01Z"
}
```

**alert.triggered Schema:**
```json
{
  "trigger_id": "uuid",
  "alert_id": "01234567-89ab-cdef-0123-456789abcdef",
  "alert_name": "Low Balance Alert",
  "execution_id": "e8283bf8-67b3-437c-9771-7ce8d69f3a26",
  "result": true,
  "value": "8.5",
  "threshold_met": "balance < 10.0 AVAX",
  "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
  "triggered_at": "2025-06-20T08:00:01Z",
  "notification_sent": false,
  "metadata": {
    "severity": "warning",
    "previous_value": "12.3",
    "change": "-3.8",
    "change_percent": "-30.89"
  }
}
```

---

### 📦 **5. BLOCK SUBJECTS**

#### **Published by:** Pipeline Service
#### **Consumed by:** Transactions Writer, Analytics

```
block.created.{network}.{subnet}     # New block detected
block.finalized.{network}.{subnet}   # Block finalized
```

**Message Schema:**
```json
{
  "block_number": 12345678,
  "block_hash": "0xblock123def456...",
  "parent_hash": "0xparent123...",
  "network": "avalanche",
  "subnet": "mainnet",
  "timestamp": "2025-06-20T08:00:00Z",
  "transaction_count": 25,
  "gas_used": "1250000",
  "gas_limit": "8000000",
  "miner": "0xminer123...",
  "difficulty": "1000000",
  "size": 2048,
  "metadata": {
    "fetcher_id": "fetcher-avalanche-mainnet",
    "processed_at": "2025-06-20T08:00:01Z",
    "source_node": "https://api.avax.network/ext/bc/C/rpc"
  }
}
```

---

### ⚙️ **6. SYSTEM SUBJECTS**

#### **Published by:** All Services
#### **Consumed by:** Monitoring, Logging

```
system.startup                   # Service started
system.shutdown                  # Service stopping
system.health                    # Health check results
system.error                     # System errors
```

**system.startup Schema:**
```json
{
  "service_name": "api",
  "service_version": "1.0.0",
  "instance_id": "api-instance-1",
  "started_at": "2025-06-20T08:00:00Z",
  "configuration": {
    "database_type": "duckdb",
    "nats_url": "nats://nats:4222",
    "environment": "development"
  },
  "metadata": {
    "hostname": "ekko-ce-api-1",
    "process_id": 1234,
    "memory_mb": 512
  }
}
```

---

## 🔄 **JETSTREAM CONFIGURATION**

### **Streams:**
```yaml
TRANSACTIONS:
  subjects: ["tx.*"]
  retention: "limits"
  max_age: "7d"
  max_bytes: "10GB"
  
ALERTS:
  subjects: ["alert.*"]
  retention: "interest"
  max_age: "30d"
  max_bytes: "1GB"
  
EVENTS:
  subjects: ["wallet.*", "node.*", "system.*"]
  retention: "limits"
  max_age: "30d"
  max_bytes: "5GB"
```

### **Consumers:**
```yaml
alert-executor:
  stream: "ALERTS"
  filter_subject: "alert.execute"
  deliver_policy: "all"
  ack_policy: "explicit"
  
transactions-writer:
  stream: "TRANSACTIONS"
  filter_subject: "tx.*"
  deliver_policy: "all"
  ack_policy: "explicit"
  
api-background:
  stream: "EVENTS"
  filter_subject: "tx.*"
  deliver_policy: "new"
  ack_policy: "explicit"
```

---

## 🔐 **SECURITY CONSIDERATIONS**

### **Message Encryption:**
- Sensitive data (private keys, API keys) should be encrypted
- Use NATS TLS for production deployments

### **Access Control:**
- Service-specific NATS users with limited permissions
- Subject-level access control

### **Message Validation:**
- All messages should include schema version
- Validate message structure before processing
- Implement message signing for critical operations

---

## 📊 **MONITORING & DEBUGGING**

### **Message Tracing:**
- Include correlation IDs in all messages
- Log message flow between services
- Track message processing times

### **Error Handling:**
- Dead letter queues for failed messages
- Retry policies with exponential backoff
- Circuit breakers for failing consumers

This reference provides comprehensive documentation for all NATS communication patterns in the Ekko CE platform. 📡
