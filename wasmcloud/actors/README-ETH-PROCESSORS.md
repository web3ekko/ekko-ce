# Ethereum Transaction Processors

This document describes the three specialized Ethereum transaction processing actors implemented following the USDT (User Story-Driven Testing) PRD methodology and wasmCloud 1.0 best practices.

## Architecture Overview

The Ethereum transaction processing pipeline consists of three specialized actors that work together to process different types of Ethereum transactions:

```
Raw Transactions (from eth_raw_transactions)
          │
          ├──→ eth_transfers_processor ──────→ transfers.processed.evm
          │                                    └→ alerts.evaluate.*
          │                                    └→ balances.updated.*
          │                                    └→ ducklake.transactions.{chain}.{subnet}.write
          │
          ├──→ eth_contract_creation_processor → contracts.deployed.evm
          │                                    └→ alerts.evaluate.*
          │                                    └→ contracts.registry.*
          │                                    └→ ducklake.transactions.{chain}.{subnet}.write
          │
          └──→ eth_contract_transaction_processor → contract-calls.processed.evm
                                               └→ alerts.evaluate.*
                                               └→ abi.decode.request
                                               └→ ducklake.contract_calls.{chain}.{subnet}.write
```

## Actors

### 1. eth_transfers_processor

**Location**: `/apps/wasmcloud/actors/eth_transfers_processor/`

**Purpose**: Process simple ETH value transfers with balance tracking and categorization.

**Input Subject**: `transfer-transactions.*.*.evm.raw`

**Output Subjects**:
- `transfers.processed.evm` - Processed transfer transactions
- `alerts.evaluate.{chain}.{subnet}` - Transfers for alert evaluation
- `balances.updated.{chain}.{subnet}` - Balance update events
- `ducklake.transactions.{chain}.{subnet}.write` - Transfers for DuckLake persistence

**Features**:
- **Wei to ETH Conversion**: Accurate conversion from Wei to ETH with proper decimal handling
- **Transfer Categorization**:
  - Micro: < 0.001 ETH
  - Small: 0.001 - 0.1 ETH
  - Medium: 0.1 - 1 ETH
  - Large: 1 - 100 ETH
  - Whale: > 100 ETH
- **Address Type Detection**: Distinguish between EOA (Externally Owned Account) and Contract addresses
- **Transaction Fee Calculation**: gas_used * gas_price with conversion to ETH
- **Balance Tracking**: Update sender/receiver balances in Redis

**Dependencies**:
- NATS Messaging (consumer, publisher)
- Redis KeyValue (balance tracking)

**WASM Size**: 231KB

**Enrichment Fields**:
```rust
{
  "transaction_type": "transfer",
  "transaction_currency": "ETH",
  "transaction_value": "1.5 ETH",
  "transaction_subtype": "native",
  "protocol": null,
  "category": "value_transfer",
  "decoded": {
    "amount_wei": "1500000000000000000",
    "amount_eth": "1.5",
    "transfer_category": "Medium",
    "from_type": "EOA",
    "to_type": "Contract",
    "transaction_fee_wei": "1050000000000000",
    "transaction_fee_eth": "0.00105"
  }
}
```

### 2. eth_contract_creation_processor

**Location**: `/apps/wasmcloud/actors/eth_contract_creation_processor/`

**Purpose**: Process contract deployments with comprehensive bytecode analysis and contract type detection.

**Input Subject**: `contract-creations.*.*.evm.raw`

**Output Subjects**:
- `contracts.deployed.evm` - Processed contract deployments
- `alerts.evaluate.{chain}` - Deployments for alert evaluation
- `contracts.registry.{chain}` - Contract registry updates
- `ducklake.transactions.{chain}.{subnet}.write` - Deployments for DuckLake persistence

**Features**:
- **Contract Address Calculation**: Implement CREATE formula: `keccak256(rlp([deployer_address, nonce]))`
- **Bytecode Analysis**:
  - Size in bytes
  - Complexity metric (unique opcodes + branch points + storage operations)
  - SHA256 hash
  - Pattern detection (proxies, upgradeable contracts)
- **Contract Type Detection**:
  - ERC20 Token: Detects transfer, approve, balanceOf functions
  - ERC721 NFT: Detects safeTransferFrom, tokenURI functions
  - Proxy Contract: Detects delegatecall patterns
  - Custom Contract: Other contract types
- **Bytecode Pattern Detection** (EIP standards):
  - **MinimalProxy (EIP-1167)**: `0x363d3d373d3d3d363d73`
  - **TransparentProxy (EIP-1967)**: `0x7f360894a13ba1a3`
  - **UUPSProxy (EIP-1822)**: `0x4e487b71`
- **Deployment Cost**: Calculate total deployment cost in Wei and ETH
- **Contract Registry**: Store contract metadata in Redis

**Dependencies**:
- NATS Messaging (consumer, publisher)
- Redis KeyValue (contract registry)

**WASM Size**: 248KB

**Enrichment Fields**:
```rust
{
  "transaction_type": "contract_deployment",
  "transaction_currency": "ETH",
  "transaction_value": "0.05 ETH",
  "transaction_subtype": "create",
  "protocol": "ERC20",
  "category": "infrastructure",
  "decoded": {
    "contract_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
    "contract_type": "ERC20Token",
    "bytecode_size": 1234,
    "bytecode_hash": "0xabcdef...",
    "bytecode_complexity": 45,
    "patterns_detected": ["MinimalProxy"],
    "deployment_cost_wei": "50000000000000000",
    "deployment_cost_eth": "0.05"
  }
}
```

### 3. eth_contract_transaction_processor

**Location**: `/apps/wasmcloud/actors/eth_contract_transaction_processor/`

**Purpose**: Process contract function calls with ABI decoding coordination and comprehensive event log processing.

**Input Subjects**:
- `contract-transactions.*.*.evm.raw` - Raw contract transactions
- `transactions.decoded.evm` - Decoded responses from ABI decoder

**Output Subjects**:
- `contract-calls.processed.evm` - Processed contract calls
- `alerts.evaluate.{chain}` - Calls for alert evaluation
- `abi.decode.request` - Decoding requests to ABI decoder
- `ducklake.contract_calls.{chain}.{subnet}.write` - Calls for DuckLake persistence

**Features**:
- **Function Selector Extraction**: Extract 4-byte function selector from input data
- **Function Categorization**:
  - Transfer, Approval, Swap, Stake, Unstake, Borrow, Repay, Liquidate, Governance, Unknown
- **Popular Function Detection** (12 functions):
  - `transfer(address,uint256)` - ERC20
  - `approve(address,uint256)` - ERC20
  - `transferFrom(address,address,uint256)` - ERC20
  - `swapExactETHForTokens(...)` - Uniswap V2
  - `swapExactTokensForTokens(...)` - Uniswap V2
  - `addLiquidity(...)` - Uniswap V2
  - `removeLiquidity(...)` - Uniswap V2
  - `stake(uint256)` - Staking protocols
  - `deposit(uint256)` - DeFi protocols
  - `borrow(uint256)` - Lending protocols
  - `mint(uint256)` - Token/NFT protocols
  - `burn(uint256)` - Token/NFT protocols
- **Event Log Processing**: Parse and categorize events (Transfer, Approval, Swap, Deposit, Withdrawal)
- **Transaction Status Detection**: Success, Failed, Reverted, OutOfGas
- **Protocol Detection**: Uniswap_V2, Aave, Compound, ERC20, ERC721, Custom
- **Category Classification**: DeFi, NFT, governance, token, infrastructure, unknown
- **Decoder Coordination**:
  - Request ABI decoding for unknown functions
  - Track pending decodes in Redis
  - Merge decoded results with original transaction
- **Dual Subscription Handling**: Listen to both raw transactions and decoded responses

**Dependencies**:
- NATS Messaging (consumer, publisher)
- Redis KeyValue (pending decode tracking)

**WASM Size**: 287KB

**Enrichment Fields**:
```rust
{
  "transaction_type": "contract_call",
  "transaction_currency": "USDT",
  "transaction_value": "100 USDT",
  "transaction_subtype": "swap",
  "protocol": "Uniswap_V2",
  "category": "defi",
  "decoded": {
    "function": {
      "selector": "0x38ed1739",
      "signature": "swapExactTokensForTokens(...)",
      "category": "swap",
      "is_popular": true
    },
    "parameters": [
      {"name": "amountIn", "type": "uint256", "value": "100000000"},
      {"name": "amountOutMin", "type": "uint256", "value": "50000000"}
    ],
    "events": [
      {
        "name": "Swap",
        "contract": "0x...",
        "parameters": {...}
      }
    ],
    "execution": {
      "status": "success",
      "gas_used": 150000
    }
  }
}
```

## Standardized Enrichment Fields

All three actors implement the same 7 standardized enrichment fields for cross-actor querying and unified analytics:

| Field | Type | Description | Example Values |
|-------|------|-------------|----------------|
| `transaction_type` | String | High-level transaction classification | `"transfer"`, `"contract_deployment"`, `"contract_call"` |
| `transaction_currency` | String | Primary currency involved | `"ETH"`, `"USDT"`, `"NONE"` |
| `transaction_value` | String | Human-readable value with unit | `"1.5 ETH"`, `"100 USDT"`, `"0"` |
| `transaction_subtype` | String | Detailed transaction classification | `"native"`, `"create"`, `"swap"`, `"stake"` |
| `protocol` | Option<String> | Protocol or standard used | `"Uniswap_V2"`, `"ERC20"`, `"Aave"`, `null` |
| `category` | String | Business domain category | `"value_transfer"`, `"defi"`, `"infrastructure"`, `"nft"`, `"governance"` |
| `decoded` | JSON | Transaction-specific decoded details | See actor-specific examples above |

## wasmCloud Configuration

### wadm Manifest Configuration

All three actors are configured in `/apps/wasmcloud/ekko-actors.wadm.yaml`:

```yaml
# Ethereum Transfers Processor Actor
- name: eth-transfers-processor
  type: component
  properties:
    image: registry.kube-system.svc.cluster.local:80/eth-transfers-processor:v1.0.0
  traits:
    - type: spreadscaler
      properties:
        instances: 2
    - type: link
      properties:
        target: nats-messaging
        namespace: wasmcloud
        package: messaging
        interfaces: [consumer, publisher]
        target_config:
          - name: eth-transfers-subscription
            properties:
              subscriptions: transfer-transactions.*.*.evm.raw
    - type: link
      properties:
        target: redis-kv
        namespace: wasmcloud
        package: keyvalue
        interfaces: [keyvalue]
```

Similar configurations exist for `eth-contract-creation-processor` (1 instance) and `eth-contract-transaction-processor` (2 instances).

### Subject Pattern Matching

All actors use wildcard subscriptions to support multiple chains and subnets:

- `transfer-transactions.*.*.evm.raw` matches:
  - `transfer-transactions.ethereum.mainnet.evm.raw`
  - `transfer-transactions.polygon.mainnet.evm.raw`
  - `transfer-transactions.arbitrum.mainnet.evm.raw`
  - etc.

## Development

### Building

```bash
# Build all actors
./build-actors.sh

# Build specific actor
cargo build --release --target wasm32-wasip1 -p eth_transfers_processor
```

### Testing

**Unit Tests**: Tests are embedded in each actor's `src/lib.rs` file but can only run in WASM environment. Test coverage designed for ~95%.

**Integration Tests**: Use the provided integration test script:

```bash
# Run integration tests
./test-eth-processors.sh
```

The integration test script:
1. Publishes test transactions to NATS
2. Subscribes to output subjects
3. Verifies processing results
4. Checks Redis state updates

### Deployment

```bash
# Deploy to wasmCloud cluster
wash app deploy ekko-actors.wadm.yaml

# Check deployment status
wash app list

# Monitor actor health
wash get inventory
```

## Redis State Management

### Balance Tracking (eth_transfers_processor)

**Key Pattern**: `balance:{address}`

**Value**: JSON object with balance information
```json
{
  "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
  "balance_wei": "1500000000000000000",
  "balance_eth": "1.5",
  "last_updated": "2024-10-17T11:55:00Z"
}
```

### Contract Registry (eth_contract_creation_processor)

**Key Pattern**: `contract:{contract_address}`

**Value**: JSON object with contract metadata
```json
{
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "type": "ERC20Token",
  "deployer": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
  "block_number": "18500001",
  "bytecode_hash": "0xabcdef...",
  "patterns": ["MinimalProxy"],
  "deployed_at": "2024-10-17T11:55:00Z"
}
```

### Pending Decodes (eth_contract_transaction_processor)

**Key Pattern**: `pending_decode:{tx_hash}`

**Value**: JSON object with pending decode request
```json
{
  "tx_hash": "0x3234567890abcdef...",
  "contract": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "input_data": "0xa9059cbb...",
  "requested_at": "2024-10-17T11:55:00Z",
  "status": "pending"
}
```

## Performance Characteristics

| Actor | Instances | Throughput Target | Latency Target | Memory |
|-------|-----------|-------------------|----------------|--------|
| eth_transfers_processor | 2 | 1,000 tx/s | <100ms | <50MB |
| eth_contract_creation_processor | 1 | 100 deployments/s | <200ms | <75MB |
| eth_contract_transaction_processor | 2 | 500 tx/s | <150ms | <100MB |

## Error Handling

All actors implement comprehensive error handling:

1. **Subject Validation**: Verify subject matches expected pattern
2. **Message Deserialization**: Validate JSON structure
3. **Processing Errors**: Catch and log processing failures
4. **Publishing Failures**: Retry with exponential backoff
5. **Redis Failures**: Graceful degradation (log error, continue processing)

## Monitoring

### NATS Subjects to Monitor

**Input Subjects** (should have steady flow):
- `transfer-transactions.*.*.evm.raw`
- `contract-creations.*.*.evm.raw`
- `contract-transactions.*.*.evm.raw`
- `transactions.decoded.evm`

**Output Subjects** (verify processing):
- `transfers.processed.evm`
- `contracts.deployed.evm`
- `contract-calls.processed.evm`
- `alerts.evaluate.*`
- `ducklake.*`

### Health Checks

```bash
# Check actor status
wash get inventory

# Check NATS subscription status
nats stream info

# Check Redis connections
redis-cli INFO clients
```

## Troubleshooting

### Actors Not Processing

1. **Check NATS subscriptions**: `wash get links`
2. **Verify subject patterns**: Ensure messages published to correct subjects
3. **Check Redis connectivity**: Verify Redis URL in configuration
4. **Review logs**: `kubectl logs -n ekko <wasmcloud-pod>`

### Processing Errors

1. **Invalid JSON**: Verify transaction structure matches expected format
2. **Missing Fields**: Check all required fields are present in raw transaction
3. **Redis Failures**: Check Redis availability and credentials

### Performance Issues

1. **Scale actors**: Increase instance count in wadm manifest
2. **Monitor memory**: Check memory usage per actor
3. **NATS backlog**: Monitor NATS stream lag
4. **Redis latency**: Check Redis response times

## Future Enhancements

1. **ERC1155 Support**: Add multi-token standard support
2. **Layer 2 Optimizations**: Optimize for L2 specific transaction patterns
3. **Advanced Analytics**: Add real-time analytics and aggregations
4. **Machine Learning**: Integrate ML models for transaction classification
5. **Cross-Chain Support**: Add support for other EVM-compatible chains

## References

- **PRDs**:
  - `/docs/prd/wasmcloud/actors/PRD-ETH-Transfers-Processor-Actor-USDT.md`
  - `/docs/prd/wasmcloud/actors/PRD-ETH-Contract-Creation-Processor-Actor-USDT.md`
  - `/docs/prd/wasmcloud/actors/PRD-ETH-Contract-Transaction-Processor-Actor-USDT.md`

- **wasmCloud Documentation**: https://wasmcloud.com/docs
- **WIT Specification**: https://component-model.bytecodealliance.org/design/wit.html
- **NATS JetStream**: https://docs.nats.io/nats-concepts/jetstream

## License

See main project LICENSE file.
