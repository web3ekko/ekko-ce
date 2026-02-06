# Redis Configuration Examples for EVM Raw Transactions Actor

This document shows how the admin interface will configure network endpoints in Redis for the `eth_raw_transactions` actor.

## How It Works

1. **Newheads Provider** sends block headers via NATS: `newheads.{network}.{subnet}.{vm_type}`
2. **Actor** receives the packet and extracts `network`, `subnet`, and `vm_type` from the payload
3. **Actor** looks up configuration in Redis using key: `nodes:{network}:{subnet}:{vm_type}`
4. **Actor** uses the configured RPC URLs to fetch transaction data
5. **Actor** publishes raw transactions to NATS

## Redis Key Structure

**Format:** `nodes:{network}:{subnet}:{vm_type}`

The key is constructed from the network information in the incoming newheads packet.

## Configuration Value Structure

```json
{
  "rpc_urls": ["https://...", "https://..."],
  "ws_urls": ["wss://...", "wss://..."],
  "chain_id": 1,
  "enabled": true
}
```

## Example Configurations

### Ethereum Mainnet
**Key:** `nodes:ethereum:mainnet:evm`

**Value:**
```json
{
  "rpc_urls": [
    "https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY",
    "https://mainnet.infura.io/v3/YOUR_PROJECT_ID",
    "https://rpc.ankr.com/eth",
    "https://ethereum.publicnode.com"
  ],
  "ws_urls": [
    "wss://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY",
    "wss://mainnet.infura.io/ws/v3/YOUR_PROJECT_ID"
  ],
  "chain_id": 1,
  "enabled": true
}
```

### Polygon Mainnet
**Key:** `nodes:polygon:mainnet:evm`

**Value:**
```json
{
  "rpc_urls": [
    "https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY",
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
    "https://polygon.publicnode.com"
  ],
  "ws_urls": [
    "wss://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY"
  ],
  "chain_id": 137,
  "enabled": true
}
```

### Arbitrum Mainnet
**Key:** `nodes:arbitrum:mainnet:evm`

**Value:**
```json
{
  "rpc_urls": [
    "https://arb-mainnet.g.alchemy.com/v2/YOUR_API_KEY",
    "https://arbitrum-one.publicnode.com",
    "https://rpc.ankr.com/arbitrum"
  ],
  "ws_urls": [
    "wss://arb-mainnet.g.alchemy.com/v2/YOUR_API_KEY"
  ],
  "chain_id": 42161,
  "enabled": true
}
```

### Ethereum Goerli (Testnet)
**Key:** `nodes:ethereum:goerli:evm`

**Value:**
```json
{
  "rpc_urls": [
    "https://eth-goerli.g.alchemy.com/v2/YOUR_API_KEY",
    "https://goerli.infura.io/v3/YOUR_PROJECT_ID",
    "https://rpc.ankr.com/eth_goerli"
  ],
  "ws_urls": [
    "wss://eth-goerli.g.alchemy.com/v2/YOUR_API_KEY"
  ],
  "chain_id": 5,
  "enabled": true
}
```

### Disabled Network Example
**Key:** `nodes:ethereum:sepolia:evm`

**Value:**
```json
{
  "rpc_urls": [
    "https://eth-sepolia.g.alchemy.com/v2/YOUR_API_KEY"
  ],
  "ws_urls": [
    "wss://eth-sepolia.g.alchemy.com/v2/YOUR_API_KEY"
  ],
  "chain_id": 11155111,
  "enabled": false
}
```

## Redis CLI Commands

To set up these configurations manually using Redis CLI:

```bash
# Ethereum Mainnet
redis-cli SET "nodes:ethereum:mainnet:evm" '{"rpc_urls":["https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY","https://mainnet.infura.io/v3/YOUR_PROJECT_ID"],"ws_urls":["wss://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"],"chain_id":1,"enabled":true}'

# Polygon Mainnet
redis-cli SET "nodes:polygon:mainnet:evm" '{"rpc_urls":["https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY","https://polygon-rpc.com"],"ws_urls":["wss://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY"],"chain_id":137,"enabled":true}'

# Arbitrum Mainnet
redis-cli SET "nodes:arbitrum:mainnet:evm" '{"rpc_urls":["https://arb-mainnet.g.alchemy.com/v2/YOUR_API_KEY"],"ws_urls":["wss://arb-mainnet.g.alchemy.com/v2/YOUR_API_KEY"],"chain_id":42161,"enabled":true}'
```

## Load Balancing

The actor currently uses the first URL in the array. Future enhancements could include:

- **Round-robin:** Cycle through URLs
- **Random selection:** Pick a random URL for each request
- **Health checking:** Remove failed URLs from rotation
- **Weighted selection:** Prefer certain providers

## Admin Interface Integration

The admin interface will provide:

1. **Web UI** for managing network configurations
2. **REST API** for programmatic configuration
3. **Validation** of URLs and chain IDs
4. **Health monitoring** of configured endpoints
5. **Bulk import/export** of configurations

## Environment Variables

For sensitive API keys, use environment variable substitution:

```json
{
  "rpc_urls": [
    "https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}",
    "https://mainnet.infura.io/v3/${INFURA_PROJECT_ID}"
  ],
  "ws_urls": [
    "wss://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}"
  ],
  "chain_id": 1,
  "enabled": true
}
```
