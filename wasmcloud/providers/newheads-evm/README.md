# 📡 Newheads EVM Provider

**wasmCloud Capability Provider** for streaming EVM blockchain newheads (new block headers) from Django-managed Ethereum Virtual Machine compatible nodes to NATS in real-time.

> **Note**: This provider is specifically designed for EVM-compatible blockchains (Ethereum, Polygon, Arbitrum, Optimism, BSC, etc.). For other blockchain types, use:
> - **UTXO chains** (Bitcoin, Litecoin): `newheads-utxo-provider`
> - **SVM chains** (Solana): `newheads-svm-provider`
> - **Cosmos chains**: `newheads-cosmos-provider`

## 🎯 **Features**

- 📡 **Real-time streaming** via WebSocket connections
- 🔗 **Multi-EVM chain support** (Ethereum, Polygon, Arbitrum, Optimism, BSC, Avalanche C-Chain)
- 🚀 **Concurrent WebSocket connections** - monitor multiple chains simultaneously
- 🔄 **Auto-reconnection** with exponential backoff
- ⚙️ **Dynamic configuration** - add/remove chains at runtime
- 📊 **Health monitoring** and connection status
- 🎯 **Actor messaging** - publishes newheads to NATS topics
- 🏗️ **Structured NATS subjects** - `newheads.{network}.{subnet}.evm`

## 🏗️ **Architecture**

```
┌─────────────────┐    Redis      ┌─────────────────┐    WebSocket   ┌─────────────────┐
│  Django Admin   │────────────►│  Newheads EVM   │◄──────────────►│   EVM Nodes     │
│  BlockchainNode │              │    Provider     │                │                 │
└─────────────────┘              └─────────────────┘                └─────────────────┘
                                         │                            Ethereum, Polygon,
                                         │ NATS                       Arbitrum, BSC, etc.
                                         ▼
                                  ┌─────────────────┐
                                  │   wasmCloud     │
                                  │    Actors       │
                                  └─────────────────┘
                                   Transaction Processors,
                                   Alert Systems, etc.
```

### Django Integration

1. **Django BlockchainNode Model** stores blockchain configurations
2. **Redis** stores configs at `blockchain:nodes:{chain_id}` keys
3. **Provider** reads from Redis and subscribes to updates via pub/sub
4. **Real-time updates** when Django admin creates/updates/deletes nodes

## 📋 **NATS Subject Structure**

### **Newheads Output: `newheads.{network}.{subnet}.evm`**

| Network | Subnet | Subject |
|---------|--------|---------|
| ethereum | mainnet | `newheads.ethereum.mainnet.evm` |
| ethereum | goerli | `newheads.ethereum.goerli.evm` |
| polygon | mainnet | `newheads.polygon.mainnet.evm` |
| arbitrum | mainnet | `newheads.arbitrum.mainnet.evm` |
| optimism | mainnet | `newheads.optimism.mainnet.evm` |
| bsc | mainnet | `newheads.bsc.mainnet.evm` |

### **Configuration Input: `config.{chain_id}.input`**

| Chain | Subject |
|-------|---------|
| ethereum-mainnet | `config.ethereum-mainnet.input` |
| polygon-mainnet | `config.polygon-mainnet.input` |
| Provider-wide | `config.provider.input` |

### **Wildcard Subscriptions**

```bash
# All EVM newheads
newheads.>

# All Ethereum chains (mainnet, goerli, sepolia)
newheads.ethereum.>

# All mainnets (Ethereum, Polygon, Arbitrum, etc.)
newheads.*.mainnet.evm

# Specific network, all subnets
newheads.polygon.*.evm
```

### **BlockHeader Message Format**

Each newheads message contains a JSON-serialized `BlockHeader` with these fields:

```json
{
  // Network identification
  "network": "ethereum",              // Network name (ethereum, polygon, arbitrum, etc.)
  "subnet": "mainnet",                // Subnet (mainnet, goerli, sepolia, etc.)
  "vm_type": "evm",                  // Always "evm" for this provider
  
  // Chain identification
  "chain_id": "ethereum-mainnet",     // Full chain identifier
  "chain_name": "Ethereum Mainnet",   // Human-readable name
  
  // Block data
  "block_number": 18500000,           // Block height as u64
  "block_hash": "0x1234...",          // Block hash (hex string)
  "parent_hash": "0xabcd...",         // Parent block hash (hex string)
  "timestamp": 1699000000,            // Unix timestamp as u64
  
  // Optional EVM-specific fields
  "difficulty": "0x1bc16d674ec80000", // Mining difficulty (hex string, optional)
  "gas_limit": 30000000,              // Gas limit (u64, optional)
  "gas_used": 15000000,               // Gas used (u64, optional)
  "miner": "0x1234567890...",         // Miner/validator address (optional)
  "extra_data": "0x...",              // Extra data field (optional)
  
  // Network-specific data
  "network_specific": {               // Additional chain-specific data
    "difficulty": "0x1bc16d674ec80000",
    "extraData": "0x..."
  },
  
  // Provider metadata
  "received_at": "2024-01-15T10:00:00Z",     // ISO 8601 timestamp
  "provider_id": "ethereum-client-ethereum-mainnet",  // Provider identifier
  
  // Node endpoint information
  "rpc_url": "https://mainnet.infura.io/v3/YOUR_KEY", // HTTP RPC endpoint
  "ws_url": "wss://mainnet.infura.io/ws/v3/YOUR_KEY", // WebSocket endpoint
  
  // Debugging
  "raw_data": "{...}"                 // Original WebSocket message (optional)
}
```

## 🚀 **Quick Start (WADM)**

### **1. Build and Package**

```bash
cd apps/wasmcloud
./build-provider.sh newheads-evm
```

### **2. WADM Manifest Entry**

```yaml
- name: newheads-evm
  type: capability
  properties:
    image: ${PROVIDER_REGISTRY}/newheads-evm:${PROVIDER_TAG}
    config:
      - name: newheads-evm-config
        properties:
          redis_url: "${REDIS_URL}"
          enabled: "true"
```

### **3. Seed Provider Config in Redis**

The provider loads its runtime configuration from Redis key `provider:config:newheads-evm`.

```bash
redis-cli -a redis123 SET provider:config:newheads-evm '{\"provider_name\":\"newheads-evm\",\"chain_id\":\"ethereum-mainnet\",\"chain_name\":\"Ethereum Mainnet\",\"network\":\"ethereum\",\"subnet\":\"mainnet\",\"vm_type\":\"evm\",\"rpc_url\":\"https://mainnet.infura.io/v3/YOUR_PROJECT_ID\",\"ws_url\":\"wss://mainnet.infura.io/ws/v3/YOUR_PROJECT_ID\",\"enabled\":true}'
```

### **4. Create BlockchainNode in Django Admin**

```python
from blockchain.models import BlockchainNode

node = BlockchainNode.objects.create(
    chain_id="ethereum-mainnet",
    chain_name="Ethereum Mainnet",
    network="ethereum",
    subnet="mainnet",
    vm_type="EVM",
    rpc_url="https://mainnet.infura.io/v3/YOUR_PROJECT_ID",
    ws_url="wss://mainnet.infura.io/ws/v3/YOUR_PROJECT_ID",
    enabled=True,
    is_primary=True,
    priority=1
)
```

### **5. Deploy via WADM**

```bash
cd apps/wasmcloud
MANIFEST_VERSION=v1.0.1 ./generate-manifest.sh
wash app put manifests/ekko-actors-generated.yaml
wash app deploy ekko-platform v1.0.1
```

### **6. Subscribe to Newheads**

```rust
// In your wasmCloud actor
use wasmcloud_interface_messaging::*;

#[async_trait]
impl MessageSubscriber for MyActor {
    async fn handle_message(&self, ctx: &Context, msg: &SubMessage) -> RpcResult<()> {
        match msg.subject.as_str() {
            "newheads.ethereum.mainnet.evm" => {
                let block_header: BlockHeader = serde_json::from_slice(&msg.body)?;
                println!("New Ethereum block: #{}", block_header.block_number);
            },
            _ => {}
        }
        Ok(())
    }
}
```

## ⚙️ **Dynamic Configuration via Django**

### **Multi-Chain Support**

The provider can monitor multiple EVM chains concurrently:

```python
# Configure multiple chains in Django
from blockchain.models import BlockchainNode

# Add Ethereum
BlockchainNode.objects.create(
    chain_id="ethereum-mainnet",
    network="ethereum", subnet="mainnet", vm_type="EVM",
    ws_url="wss://mainnet.infura.io/ws/v3/YOUR_KEY",
    enabled=True
)

# Add Polygon
BlockchainNode.objects.create(
    chain_id="polygon-mainnet", 
    network="polygon", subnet="mainnet", vm_type="EVM",
    ws_url="wss://polygon-mainnet.infura.io/ws/v3/YOUR_KEY",
    enabled=True
)

# Add Arbitrum
BlockchainNode.objects.create(
    chain_id="arbitrum-mainnet",
    network="arbitrum", subnet="mainnet", vm_type="EVM", 
    ws_url="wss://arbitrum-mainnet.infura.io/ws/v3/YOUR_KEY",
    enabled=True
)

# Provider will automatically connect to all enabled chains
```

### **Django Admin Interface**

1. Navigate to Django Admin: `http://localhost:8000/admin/`
2. Go to Blockchain → Blockchain Nodes
3. Add/Edit/Delete nodes as needed
4. Provider automatically detects changes via Redis pub/sub
5. Multiple chains run concurrently via async tasks

### **Django Management Commands**

```bash
# List all nodes
python manage.py list_blockchain_nodes

# Add a new node
python manage.py add_blockchain_node \
  --chain-id polygon-mainnet \
  --network polygon \
  --subnet mainnet \
  --vm-type EVM \
  --rpc-url https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID \
  --ws-url wss://polygon-mainnet.infura.io/ws/v3/YOUR_PROJECT_ID

# Enable a node
python manage.py enable_blockchain_node ethereum-mainnet

# Disable a node
python manage.py disable_blockchain_node ethereum-mainnet
```

### **Redis Pub/Sub Updates**

The provider listens to `blockchain:nodes:updates` channel:

```json
{
  "action": "create|update|delete",
  "chain_id": "ethereum-mainnet",
  "timestamp": "2024-01-15T10:00:00Z"
}
```

### **Monitor Updates**

```bash
# Subscribe to updates
redis-cli SUBSCRIBE "blockchain:nodes:updates"

# View stored nodes
redis-cli KEYS "blockchain:nodes:*"
redis-cli GET "blockchain:nodes:ethereum-mainnet"
```

## 🔧 **Supported EVM Chains**

This provider exclusively supports Ethereum Virtual Machine compatible blockchains:

### **Ethereum & Layer 1s**
- ✅ Ethereum (Mainnet, Goerli, Sepolia)
- ✅ Binance Smart Chain (BSC)
- ✅ Avalanche C-Chain

### **Layer 2 Solutions**
- ✅ Polygon (Mainnet, Mumbai)
- ✅ Arbitrum One
- ✅ Optimism
- 🔄 Base - *In Progress*
- 🔄 zkSync Era - *In Progress*

### **Other Blockchain Types**
For non-EVM blockchains, use the appropriate specialized providers:
- **UTXO chains** (Bitcoin, Litecoin): Use `newheads-utxo-provider`
- **SVM chains** (Solana): Use `newheads-svm-provider`
- **Cosmos chains**: Use `newheads-cosmos-provider`

## 📊 **Monitoring**

### **Provider Logs**
```bash
wash app status ekko-platform
kubectl logs -n ekko -l app.kubernetes.io/component=wasmcloud-host | rg newheads
```

### **NATS Monitoring**
```bash
# Monitor all EVM newheads from all chains
nats sub "newheads.>"

# Monitor specific network (all subnets)
nats sub "newheads.ethereum.>"

# Monitor multiple specific chains
nats sub "newheads.ethereum.mainnet.evm" "newheads.polygon.mainnet.evm"
```

### **Django Health Checks**
```python
# Check node health in Django
from blockchain.models import BlockchainNode

for node in BlockchainNode.objects.filter(enabled=True):
    print(f"{node.chain_id}: {node.latency_ms}ms, {node.success_rate}%")
```

## 🛠️ **Development**

### **Adding a New Blockchain**

1. **Add chain configuration** in `config/chains.toml`
2. **Implement client** in `src/{blockchain}.rs`
3. **Update traits** if needed for new VM type
4. **Test connection** and newheads streaming
5. **Update documentation**

### **Testing**

```bash
# Run all tests
cargo test

# Django integration tests
cargo test --test django_integration_test
cargo test --test django_lifecycle_test

# Multi-chain WebSocket tests
cargo test --test multiple_websocket_test

# Verify WADM deployment
cd apps/wasmcloud
./verify-wadm-deployment.sh
```

## 🔒 **Security**

- **Capability-based** access control via wasmCloud
- **Environment variables** for sensitive API keys
- **Rate limiting** on configuration endpoints
- **Input validation** for all configuration data

## 🔧 **Troubleshooting**

### Provider Exits Immediately (Status 0) in Kubernetes/OrbStack

**Problem**: The provider starts and immediately exits with status 0 (success) when deployed to Kubernetes or OrbStack environments.

**Root Cause**: The provider was originally using stdin monitoring to detect shutdown signals from wasmCloud. However, in Kubernetes/OrbStack container environments, stdin is either not connected or is immediately closed by the container runtime. This causes the provider to interpret stdin closure as a shutdown signal and exit.

**Symptoms**:
- Provider logs show: `[SIGNAL] stdin closed (EOF) - wasmCloud requested shutdown`
- Exit happens within microseconds of startup
- Provider works fine in local development but fails in Kubernetes

**Solution** (Applied in v1.0.3+): The provider now uses Unix signals (SIGTERM/SIGINT) instead of stdin monitoring for shutdown detection:

```rust
// OLD (broken in Kubernetes):
let stdin_closed = async {
    let mut stdin = tokio::io::stdin();
    let mut buf = [0u8; 1];
    loop {
        match stdin.read(&mut buf).await {
            Ok(0) => break,  // stdin closed = shutdown
            // ...
        }
    }
};

// NEW (works in Kubernetes):
use tokio::signal::unix::{signal, SignalKind};

let mut sigterm = signal(SignalKind::terminate())?;
let mut sigint = signal(SignalKind::interrupt())?;

tokio::select! {
    _ = sigterm.recv() => { /* SIGTERM received */ }
    _ = sigint.recv() => { /* SIGINT received */ }
}
```

**Verification**: After updating to v1.0.3+, you should see:
```
[MAIN] Waiting for shutdown signal (SIGTERM or SIGINT)...
[MAIN] Provider will run until killed by wasmCloud or Kubernetes
```

**Important**: Always use provider version v1.0.3 or later when deploying to Kubernetes/OrbStack.

### Missing Configuration Error

**Problem**: Provider fails to start with error: `Config newheads-evm-config does not exist`

**Root Cause**: The WADM manifest is missing the `newheads-evm-config` block or the manifest was generated without required values.

**Solution**: Ensure `apps/wasmcloud/manifests/ekko-actors.template.yaml` includes the provider config and regenerate the manifest:

```bash
cd apps/wasmcloud
MANIFEST_VERSION=v1.0.1 ./generate-manifest.sh
wash app put manifests/ekko-actors-generated.yaml
wash app deploy ekko-platform v1.0.1
```

### Provider Not Appearing in Inventory

**Problem**: After deployment, provider doesn't appear in `wash get inventory`

**Solution**:
1. Check WADM application status: `wash app status ekko-platform`
2. Check wasmCloud host logs: `kubectl logs -n ekko -l app.kubernetes.io/name=wasmcloud-host`
3. Verify the provider image exists in registry
4. Ensure configs were created before deployment

## 📚 **Documentation**

- [wasmCloud Provider SDK](https://wasmcloud.dev/docs/developer/providers/)
- [NATS Messaging](https://docs.nats.io/)
- [WebSocket Connections](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 **License**

This project is licensed under the MIT License.
