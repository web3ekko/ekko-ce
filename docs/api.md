# API Reference

## DSPy Job Specification Generator

### Overview

The API uses DSPy to convert natural language alert queries into structured job specifications with Polars code.

### Key Components

- `dspy_job_generator.py` - Main DSPy implementation
- `alert_job_utils.py` - Integration with alert system
- Background task for job spec generation

### Usage

When an alert is created with a natural language query, DSPy automatically generates a job specification that can be executed by external job runners.

## Redis Data Structures

### Alert Rules
```
Key: alert:{blockchain_symbol}:{wallet_id}
Type: Hash
Fields:
  - id: Unique alert ID
  - wallet_id: Target wallet ID
  - blockchain_symbol: Chain identifier (avax-c, avax-p)
  - conditions: JSON string of alert conditions
  - status: active/inactive
  - created_at: Timestamp
```

### Notifications
```
Stream: notifications:{blockchain_symbol}:{wallet_id}
Entry:
  - alert_id: Alert that triggered
  - transaction_hash: Transaction hash
  - timestamp: Event time
  - details: JSON of transaction details
```

## MinIO Storage

### Transaction Data
```
Bucket: ekko
Path: raw_transactions/{timestamp}_{uuid}.json
Content: Full transaction data with metadata
```

## Streamlit Components

### Alert Management
```python
def create_alert(alert_data: Dict[str, Any]) -> str:
    """Create a new alert rule"""
    
def list_alerts(wallet_id: str = None) -> List[Dict]:
    """List all alerts, optionally filtered by wallet"""
    
def update_alert(alert_id: str, data: Dict[str, Any]) -> bool:
    """Update an existing alert"""
```

### Wallet Management
```python
def add_wallet(wallet_data: Dict[str, Any]) -> str:
    """Add a new wallet to monitor"""
    
def get_wallet_transactions(wallet_id: str) -> List[Dict]:
    """Get transaction history for a wallet"""
```

## WebSocket Subscriptions

### New Transactions
```json
{
  "jsonrpc": "2.0",
  "method": "eth_subscribe",
  "params": ["newPendingTransactions"],
  "id": 1
}
```

### Response Format
```json
{
  "jsonrpc": "2.0",
  "method": "eth_subscription",
  "params": {
    "subscription": "0x...",
    "result": "0x..." // Transaction hash
  }
}
```
