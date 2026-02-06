#!/bin/bash
set -e

echo "🌱 Seeding Redis with Network Configurations"
echo "============================================="
echo ""

REDIS_HOST="redis-master.ekko.svc.cluster.local"
REDIS_PORT="6379"
REDIS_PASSWORD="redis123"

# Ethereum Mainnet EVM Configuration
echo "📝 Setting Ethereum Mainnet EVM config..."
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD SET "nodes:ethereum:mainnet:evm" '{
  "network": "ethereum",
  "subnet": "mainnet",
  "vm_type": "evm",
  "chain_id": "1",
  "rpc_url": "https://eth-mainnet.g.alchemy.com/v2/demo",
  "ws_url": "wss://eth-mainnet.g.alchemy.com/v2/demo",
  "fallback_rpc_urls": [
    "https://cloudflare-eth.com",
    "https://ethereum.publicnode.com"
  ],
  "block_time_ms": 12000,
  "confirmations_required": 12
}' > /dev/null
echo "✅ Ethereum config set"

# Bitcoin Mainnet Configuration
echo "📝 Setting Bitcoin Mainnet config..."
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD SET "nodes:bitcoin:mainnet:btc" '{
  "network": "bitcoin",
  "subnet": "mainnet",
  "vm_type": "btc",
  "chain_id": "bitcoin-mainnet",
  "rpc_url": "https://bitcoin.blockstream.com/api",
  "block_time_ms": 600000,
  "confirmations_required": 6
}' > /dev/null
echo "✅ Bitcoin config set"

# Solana Mainnet SVM Configuration
echo "📝 Setting Solana Mainnet SVM config..."
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD SET "nodes:solana:mainnet:svm" '{
  "network": "solana",
  "subnet": "mainnet",
  "vm_type": "svm",
  "chain_id": "solana-mainnet-beta",
  "rpc_url": "https://api.mainnet-beta.solana.com",
  "ws_url": "wss://api.mainnet-beta.solana.com",
  "block_time_ms": 400,
  "confirmations_required": 32
}' > /dev/null
echo "✅ Solana config set"

echo ""
echo "============================================="
echo "✅ All network configurations seeded successfully"
echo "============================================="
echo ""
echo "📊 Verification:"
echo "  - Ethereum: redis-cli -h $REDIS_HOST -a $REDIS_PASSWORD GET nodes:ethereum:mainnet:evm"
echo "  - Bitcoin:  redis-cli -h $REDIS_HOST -a $REDIS_PASSWORD GET nodes:bitcoin:mainnet:btc"
echo "  - Solana:   redis-cli -h $REDIS_HOST -a $REDIS_PASSWORD GET nodes:solana:mainnet:svm"
