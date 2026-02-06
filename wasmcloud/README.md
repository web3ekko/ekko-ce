# Ekko WasmCloud Platform

## Quick Start - Automated Deployment

Deploy the entire Ekko platform to OrbStack in one command:

```bash
# From project root
./scripts/deployment/deploy .env.orbstack
```

**Duration**: 5-10 minutes
**Requirements**: orbstack, kubectl, helm, docker
**Optional**: wash CLI for wasmCloud management

### WasmCloud-Focused Deployment (via the main deploy script)

For wasmCloud-only iterations, use the main deploy script with appropriate flags:

```bash
# From project root (skip API/dashboard, keep wasmCloud + infra)
./scripts/deployment/deploy .env.orbstack --skip-applications
```

**Common flags**:
```bash
SKIP_BUILD=true ./scripts/deployment/deploy .env.orbstack   # Skip image builds
DRY_RUN=true ./scripts/deployment/deploy .env.orbstack      # Preview only
./scripts/deployment/deploy .env.orbstack --skip-actors     # Skip wasmCloud actors/providers
```

## What Gets Deployed

### Infrastructure
- NATS with JetStream
- Redis (key-value store)
- PostgreSQL (primary database)

### WasmCloud Platform (Official Chart)
- wasmCloud Operator
- WADM (Application Deployment Manager)
- wasmCloud Hosts

### Ekko Services
- API (Django REST API)
- Dashboard (React frontend)

### Ekko Actors (via WADM)
- 3 essential actors (local OrbStack)
- Standard capability providers (NATS, Redis)

## Architecture

```
┌─────────────────────────────────────────────────┐
│           OrbStack Cluster (ekko namespace)     │
│                                                  │
│  Infrastructure Layer:                          │
│  ├─ NATS (JetStream)                            │
│  ├─ Redis                                       │
│  └─ PostgreSQL                                  │
│                                                  │
│  WasmCloud Platform (Official):                 │
│  ├─ Operator                                    │
│  ├─ WADM                                        │
│  └─ Hosts                                       │
│                                                  │
│  Ekko Services:                                 │
│  ├─ API                                         │
│  └─ Dashboard                                   │
│                                                  │
│  Ekko Actors (WADM-Deployed):                   │
│  ├─ eth-raw-transactions                        │
│  ├─ alert-processor                             │
│  ├─ health-check                                │
│  └─ Standard Providers (NATS, Redis)            │
└─────────────────────────────────────────────────┘
```

## Directory Structure

```
wasmcloud/
├── actors/                    # wasmCloud actors (business logic)
│   ├── eth_raw_transactions/  # EVM raw transaction processor
│   ├── btc_raw_transactions/  # UTXO raw transaction processor
│   ├── sol_raw_transactions/  # SVM raw transaction processor
│   ├── eth_process_transactions/  # Ethereum-specific processing
│   ├── alert-processor/       # Alert and notification processing
│   ├── health-check/          # Health monitoring actor
│   ├── notification-router/   # Notification delivery
│   ├── transaction-ducklake-writer/  # DuckLake storage
│   ├── transaction-processor/ # Generic transaction processing
│   └── abi-decoder/           # ABI decoding
├── providers/                 # Custom capability providers
│   ├── newheads-evm/         # Blockchain newheads streaming
│   ├── ducklake-write/       # DuckLake write provider
│   ├── ducklake-read/        # DuckLake read provider
│   ├── alert-scheduler/      # Alert scheduling provider
│   └── websocket-notification-provider/  # WebSocket notifications
├── manifests/                 # WADM deployment manifests
│   ├── ekko-actors.yaml      # Full deployment (10 actors)
│   └── ekko-actors-generated.yaml  # Local deployment (generated)
├── chart/                     # Helm chart
│   ├── Chart.yaml            # Chart definition with official dependency
│   ├── values.official.yaml  # Upstream reference configuration
│   ├── values.yaml           # Local configuration
│   ├── values.production.yaml  # Production configuration
│   └── templates/            # Helm templates
└── shared/                    # Shared libraries
    └── notification-common/  # Common notification code
```

## Key Features

### ✅ Unified OCI Registry Approach
Consistent deployment workflow across all environments using OCI registry pattern:
- **Development**: docker-compose registry (`localhost:5001` / `host.docker.internal:5001`)
- **Staging/Production**: GitLab Container Registry
- **Benefits**: No file copying, automatic distribution, version control, CI/CD integration

**Workflow**:
```
Build → Push to OCI Registry → Generate Manifest → Deploy via WADM
```

### ✅ Official wasmCloud Integration
Uses official `wasmcloud-platform` Helm chart from `oci://ghcr.io/wasmcloud/charts`

**Benefits**:
- Maintained by wasmCloud team
- Production-tested
- Regular security updates
- Consistent with best practices

### ✅ Templated Manifests
Environment-specific configuration via variable substitution:
- `manifests/ekko-actors.template.yaml` - Single source of truth
- `manifests/ekko-actors-generated.yaml` - Generated with actual registry URLs
- Supports multiple environments with same template

### ✅ Resource Optimization
OrbStack-specific configuration:
- 76% CPU reduction
- 85% memory reduction
- Only essential actors enabled

### ✅ Comprehensive Automation
- Zero manual steps
- Automatic error handling
- OCI registry fallback
- Health validation

## Data Flow

```
Blockchain Nodes → Newheads Provider → NATS → Raw Transaction Actors →
Processing Actors → Alert Processor → Notification Router → Users
```

### Detailed Flow

1. **Newheads Provider** connects to blockchain nodes via WebSocket
2. **Publishes** block headers to `newheads.{network}.{subnet}.{vm_type}` NATS subjects
3. **Raw Transaction Actors** subscribe to `newheads.*.*.{vm_type}` (wildcard by VM type)
4. **Fetch transactions** for each block and publish to `blockchain.{chain}.transactions.raw`
5. **Processing Actors** subscribe to raw transactions and apply network-specific logic
6. **Alert Processor** evaluates alerts and publishes to `alerts.process`
7. **Notification Router** delivers alerts via configured channels

## NATS Subject Patterns

### Blockchain Data
Subject pattern: `blockchain.{network}.{subnet}.transactions.{stage}`

**Subscription Patterns (wildcards for handlers):**
- `blockchain.ethereum.>.transactions.raw` - Raw Ethereum transactions (all subnets)
- `blockchain.bitcoin.>.transactions.raw` - Raw Bitcoin transactions (all subnets)
- `blockchain.solana.>.transactions.raw` - Raw Solana transactions (all subnets)
- `blockchain.>.>.transactions.>` - All blockchain transactions

**Publishing Patterns (specific network/subnet):**
- `blockchain.ethereum.mainnet.transactions.raw` - Mainnet Ethereum raw transactions
- `blockchain.ethereum.sepolia.transactions.raw` - Sepolia testnet raw transactions
- `blockchain.ethereum.mainnet.transactions.processed` - Processed mainnet Ethereum data

### Alerts & Notifications
- `alerts.process` - Alert processing
- `notifications.route` - Notification routing
- `system.health` - Health check data

## Common Operations

### Check Deployment Status

```bash
# Check all pods
kubectl get pods -n ekko

# Check services
kubectl get svc -n ekko

# View logs
kubectl logs -n ekko -l app=ekko-api --tail=50 -f
```

### Check WasmCloud Status

```bash
# Port-forward to control plane
kubectl port-forward -n ekko svc/ekko-wasmcloud 4223:4223

# In another terminal:
wash get hosts
wash get inventory
wash app list
wash app status ekko-platform
```

### Access Services

```bash
# Use access helper (recommended)
./scripts/access-services.sh
```

### Deploy Additional Actors

```bash
# Enable more actors in values file
helm upgrade ekko-wasmcloud chart \
    --namespace ekko \
    --values chart/values.yaml

# Or deploy via WADM
wash app deploy manifests/ekko-actors.yaml
```

## Deployment Scripts

### Overview

The platform provides multiple deployment scripts for different use cases:

| Script | Purpose | Environment | Use Case |
|--------|---------|-------------|----------|
| `scripts/deployment/deploy` | Full-stack deployment (infra + wasmCloud + apps) | Any | **Recommended for all deployments** |
| `build.sh` | Build all actors | N/A | Part of unified workflow |
| `push-actors-to-registry.sh` | Push actors to OCI registry | Any | Part of unified workflow |
| `generate-manifest.sh` | Generate WADM manifest from template | Any | Part of unified workflow |

### scripts/deployment/deploy

**Unified deployment script** for the entire stack:

```bash
# Local OrbStack deployment
./scripts/deployment/deploy .env.orbstack

# Production deployment
./scripts/deployment/deploy .env.production

# Preview changes without deploying
DRY_RUN=true ./scripts/deployment/deploy .env.orbstack

# Skip phases
SKIP_BUILD=true ./scripts/deployment/deploy .env.orbstack
./scripts/deployment/deploy .env.orbstack --skip-applications
./scripts/deployment/deploy .env.orbstack --skip-actors
```

**What it does**:
1. Loads and validates the environment file
2. Builds images/artifacts (unless `SKIP_BUILD=true`)
3. Deploys infrastructure (Kubernetes + Helm)
4. Deploys wasmCloud actors/providers (unless `--skip-actors`)
5. Deploys API/dashboard apps (unless `--skip-applications`)

### Environment Configuration Files

- **`.env.orbstack`** - Local OrbStack settings
- **`.env.development`** - Development settings
- **`.env.production`** - Production settings

**Example** (`.env.orbstack`):
```bash
ENVIRONMENT=orbstack
MANIFEST_VERSION=v1.0.0
ACTOR_REGISTRY=host.docker.internal:5001
ACTOR_TAG=v1.0.0
```

### Manual Workflow

For understanding the process or custom workflows:

```bash
# 1. Build actors
./build.sh

# 2. Setup registry (development only)
cd ../..
docker-compose up -d registry
cd apps/wasmcloud

# 3. Push to registry
export ACTOR_REGISTRY=localhost:5001
export ACTOR_TAG=v1.0.0
./push-actors-to-registry.sh

# 4. Generate manifest
export ENVIRONMENT=development
export MANIFEST_VERSION=v1.0.0
export ACTOR_REGISTRY=host.docker.internal:5001
./generate-manifest.sh

# 5. Deploy via WADM
kubectl port-forward -n ekko svc/nats 4222:4222 4223:4223 &
wash app put manifests/ekko-actors-generated.yaml
wash app deploy ekko-platform v1.0.0
```

## Development

### Building Actors

```bash
# Build all actors
cd actors
make build

# Build specific actor
cd actors/eth_raw_transactions
cargo build --release --target wasm32-wasip1
```

### Testing Actors

```bash
# Run unit tests
cargo test

# Run integration tests
cargo test --test integration_tests
```

### Adding New Actors

1. **Create actor directory**:
```bash
cd actors
cargo new --lib my_new_actor
```

2. **Define in values file**:
```yaml
actors:
  - name: my-new-actor
    enabled: true
    wasmPath: actors/my_new_actor
    wasmFile: my_new_actor_s.wasm
    capabilities:
      - messaging
      - keyvalue
    config:
      natsSubject: my.subject
```

3. **Build and deploy**:
```bash
cd actors/my_new_actor
cargo build --release --target wasm32-wasip1
../../scripts/deployment/deploy .env.orbstack
```

## Troubleshooting

### OCI Registry Issues

If Helm fails to pull the official chart, the script automatically:
1. Falls back to manual download
2. Uses local chart tarball
3. Continues deployment

**Manual fix**:
```bash
cd apps/wasmcloud/chart
helm pull oci://ghcr.io/wasmcloud/charts/wasmcloud-platform \
    --version 0.4.0 --untar --untardir charts/
```

### Actors Not Starting

```bash
# Check WADM logs
kubectl logs -n ekko -l app.kubernetes.io/component=wadm

# Check wasmCloud hosts
kubectl logs -n ekko -l app.kubernetes.io/component=wasmcloud-host

# Manually deploy manifest
wash app deploy manifests/ekko-actors-generated.yaml
```

### Resource Constraints

```bash
# Check resources
kubectl top nodes
kubectl top pods -n ekko

# Increase OrbStack resources
orbstack stop
orbstack start --memory=10240 --cpus=6
```

## Cleanup

```bash
# Stop (preserve data)
orbstack stop

# Delete everything
orbstack delete

# Uninstall selectively
helm uninstall ekko-wasmcloud -n ekko
```

## Documentation

- **Automated Deployment Guide**: `/docs/deployment/WASMCLOUD-AUTOMATED-DEPLOYMENT.md`
- **Deployment Guide**: `/docs/deployment/WASMCLOUD-DEPLOYMENT.md`
- **Migration Guide**: `/docs/deployment/WASMCLOUD-MIGRATION-GUIDE.md`
- **Simplification Summary**: `/docs/deployment/WASMCLOUD-SIMPLIFICATION-SUMMARY.md`
- **Chart README**: `chart/README.md`
- **Official wasmCloud Docs**: https://wasmcloud.com/docs

## Support

For issues or questions:
1. Check documentation above
2. Review wasmCloud docs: https://wasmcloud.com/docs
3. Check logs: `kubectl logs -n ekko`
4. Contact: team@ekko.zone

## License

Copyright © 2024 Ekko Platform
