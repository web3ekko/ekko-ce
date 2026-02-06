# Ekko WasmCloud Helm Chart

**Simplified and Consolidated WasmCloud Deployment**

## Overview

This Helm chart deploys the Ekko wasmCloud platform with a **consolidated, loop-based configuration** approach that replaces 10+ individual ConfigMap files with a single, maintainable structure.

### Key Features

- ✅ **90% Less Code**: 30 lines vs 400+ lines of repetitive YAML
- ✅ **Single Source of Truth**: All actors defined in values.yaml
- ✅ **Automatic Provider Linking**: Actors auto-link based on capabilities
- ✅ **WADM Integration**: Declarative application deployment
- ✅ **Easy Actor Addition**: Just add to values, no new files needed
- ✅ **Environment-Specific Overrides**: OrbStack vs Production values

---

## Quick Start

### Deploy to OrbStack

```bash
# Using Helm directly
helm install ekko-wasmcloud apps/wasmcloud/chart \
    --namespace ekko \
    --values apps/wasmcloud/chart/values.production.yaml \
    --create-namespace
```

### Deploy to Production

```bash
helm install ekko-wasmcloud apps/wasmcloud/chart \
    --namespace ekko \
    --values apps/wasmcloud/chart/values.yaml \
    --create-namespace
```

---

## Chart Structure

```
chart/
├── Chart.yaml                      # Chart metadata
├── values.yaml                     # Local defaults (OrbStack)
├── values-new.yaml                 # New consolidated structure (reference)
├── values.production.yaml          # Production overrides
├── templates/
│   ├── _helpers.tpl                # Reusable template helpers
│   ├── actors-configmap.yaml       # Consolidated actor ConfigMaps (loops)
│   ├── providers-configmap.yaml    # Consolidated provider ConfigMaps (loops)
│   ├── wadm-manifest.yaml          # Auto-generated WADM manifest
│   ├── deployment.yaml             # WasmCloud host deployment
│   ├── service.yaml                # WasmCloud services
│   └── deprecated/                 # Old individual ConfigMap files (archived)
│       ├── eth-actor-configmap.yaml
│       ├── btc-actor-configmap.yaml
│       └── ... (10+ files)
└── README.md                       # This file
```

---

## Configuration

### Actor Definition

Actors are defined as a list in `values.yaml`:

```yaml
actors:
  - name: eth-raw-transactions
    enabled: true
    replicas: 1
    wasmPath: actors/eth_raw_transactions
    wasmFile: eth_raw_transactions_s.wasm
    description: "Processes raw Ethereum transaction data"
    capabilities:
      - messaging  # Auto-links to NATS provider
      - keyvalue   # Auto-links to Redis provider
    config:
      # Subject pattern: blockchain.{network}.{subnet}.transactions.{stage}
      # Wildcard > catches all subnets (mainnet, sepolia, etc.)
      natsSubject: blockchain.ethereum.>.transactions.raw
      redisKeyPrefix: eth:raw
```

**What This Does**:
1. Generates ConfigMap: `ekko-wasmcloud-eth-raw-transactions-config`
2. Adds entry to WADM manifest: `ekko-platform.yaml`
3. Auto-creates links to NATS and Redis based on capabilities
4. Applies resource limits from `resources.actors`
5. Includes monitoring and health checks

### Provider Definition

Standard providers (NATS, Redis):
```yaml
providers:
  standard:
    nats:
      enabled: true
      replicas: 1
      image: ghcr.io/wasmcloud/messaging-nats:0.23.0
      config:
        clusterUris:
          - nats://nats.ekko.svc.cluster.local:4222
```

Custom providers:
```yaml
providers:
  custom:
    newheads:
      enabled: true
      replicas: 1
      imagePath: providers/newheads-evm
      imageFile: newheads-provider
      config:
        networks:
          - name: ethereum-mainnet
            chain: ethereum
```

### Capability Linking

Actors automatically link to providers based on their `capabilities` array:

| Capability | Provider | Contract | Interfaces |
|------------|----------|----------|------------|
| `messaging` | NATS | wasmcloud:messaging | consumer, publisher |
| `keyvalue` | Redis | wasi:keyvalue | store |
| `ducklake` | DuckLake | ekko:ducklake | ducklake |
| `websocket` | WebSocket | ekko:websocket | sender |

---

## Adding a New Actor

### Step 1: Add to values.yaml

```yaml
actors:
  - name: my-custom-actor
    enabled: true
    replicas: 1
    wasmPath: actors/my_custom_actor
    wasmFile: my_custom_actor_s.wasm
    description: "My custom blockchain actor"
    capabilities:
      - messaging
      - keyvalue
    config:
      natsSubject: blockchain.custom.events
      redisKeyPrefix: custom:data
```

### Step 2: Deploy

```bash
helm upgrade ekko-wasmcloud apps/wasmcloud/chart \
    --namespace ekko \
    --values apps/wasmcloud/chart/values.yaml
```

**That's it!** The template automatically:
- Creates ConfigMap with actor configuration
- Generates WADM manifest entry
- Links actor to NATS and Redis providers
- Applies resource limits
- Includes in monitoring

---

## Environment-Specific Configuration

### OrbStack (Development)

`values.yaml`:
- ✅ Reduced resource limits (200m CPU, 128Mi RAM)
- ✅ Only essential actors enabled
- ✅ Custom providers disabled (save resources)
- ✅ Debug logging enabled
- ✅ Single replicas

### Production

`values.production.yaml`:
- ✅ Full resource limits (250m CPU, 256Mi RAM)
- ✅ All actors enabled
- ✅ Custom providers enabled
- ✅ Info-level logging
- ✅ Horizontal scaling (3+ replicas)
- ✅ Autoscaling enabled

---

## Template Helpers

The chart includes reusable helpers in `_helpers.tpl`:

```yaml
# Generate NATS URL with fallback
{{- include "wasmcloud.natsUrl" . }}

# Generate Redis URL with fallback
{{- include "wasmcloud.redisUrl" . }}

# Generate actor WASM path
{{- include "wasmcloud.actorWasmPath" $actor }}

# Check if actor has capability
{{- include "wasmcloud.hasCapability" (list $actor "messaging") }}

# Generate actor resource configuration
{{- include "wasmcloud.actorResources" . }}
```

---

## WADM Manifest

The WADM manifest (`wadm-manifest.yaml`) is automatically generated from values and includes:

- **Components**: Actors and providers
- **Traits**: Spreadscaling, linking, configuration
- **Policies**: Health monitoring, resource limits, autoscaling

### View Generated Manifest

```bash
kubectl get configmap -n ekko ekko-wasmcloud-wadm-manifest -o yaml
```

### Manual Deployment

```bash
kubectl get configmap -n ekko ekko-wasmcloud-wadm-manifest \
    -o jsonpath='{.data.ekko-platform\.yaml}' | wash app deploy -
```

---

## Comparison: Old vs New

### Old Approach

**Files**: 10+ individual ConfigMap files
```
templates/
├── eth-actor-configmap.yaml (53 lines)
├── btc-actor-configmap.yaml (10 lines)
├── sol-actor-configmap.yaml (10 lines)
├── alert-processor-configmap.yaml (10 lines)
├── ... (6 more files)
└── wadm-configmap.yaml (222 lines)
```

**To Add Actor**: Create new file, copy-paste, modify, test, merge

**Total**: ~400+ lines of YAML

### New Approach

**Files**: 3 consolidated templates
```
templates/
├── actors-configmap.yaml (30 lines, loops all actors)
├── providers-configmap.yaml (30 lines, loops all providers)
└── wadm-manifest.yaml (auto-generated from values)
```

**To Add Actor**: Add 10 lines to values.yaml

**Total**: ~60 lines of template code

**Savings**: 90% less code, single source of truth

---

## Values Schema

```yaml
# Global Configuration
global:
  environment: string  # development, staging, production
  namespace: string

# WasmCloud Configuration
wasmcloud:
  host:
    replicas: int
    latticePrefix: string
    logLevel: string  # debug, info, warn, error
    nats:
      url: string
      jsDomain: string
    labels: map[string]string

  operator:
    enabled: bool
    image:
      repository: string
      tag: string

  wadm:
    enabled: bool
    image:
      repository: string
      tag: string

# Actors (list)
actors:
  - name: string
    enabled: bool
    replicas: int
    wasmPath: string
    wasmFile: string
    description: string
    capabilities: []string  # messaging, keyvalue, storage, websocket
    config: map[string]any

# Providers
providers:
  standard:
    nats:
      enabled: bool
      replicas: int
      image: string
      config: map[string]any
    redis:
      enabled: bool
      replicas: int
      image: string
      config: map[string]any

  custom:
    [provider-name]:
      enabled: bool
      replicas: int
      imagePath: string
      imageFile: string
      config: map[string]any

# Resources
resources:
  host:
    limits: {cpu: string, memory: string}
    requests: {cpu: string, memory: string}
  actors:
    limits: {cpu: string, memory: string}
    requests: {cpu: string, memory: string}
  providers:
    limits: {cpu: string, memory: string}
    requests: {cpu: string, memory: string}

# Monitoring
monitoring:
  enabled: bool
  prometheus:
    enabled: bool
    port: int
    scrapeInterval: string

# Autoscaling
autoscaling:
  enabled: bool
  minReplicas: int
  maxReplicas: int
  targetCPUUtilizationPercentage: int
  targetMemoryUtilizationPercentage: int
```

---

## Troubleshooting

### Actors Not Starting

```bash
# Check logs
kubectl logs -n ekko -l app.kubernetes.io/component=actor --tail=50

# Verify ConfigMap exists
kubectl get configmap -n ekko | grep actor-config

# Check WADM manifest
kubectl get configmap -n ekko ekko-wasmcloud-wadm-manifest -o yaml
```

### Provider Links Not Working

```bash
# Verify capabilities in values.yaml
actors:
  - name: my-actor
    capabilities:
      - messaging  # Must match provider type

# Check wash link status
wash get links
```

### WADM Not Deploying

```bash
# Check WADM logs
kubectl logs -n ekko -l app.kubernetes.io/component=wadm

# Manually deploy
wash app deploy ekko-platform.yaml

# Check status
wash app status ekko-platform
```

---

## Documentation

- **Deployment Guide**: `/docs/deployment/WASMCLOUD-DEPLOYMENT.md`
- **Migration Guide**: `/docs/deployment/WASMCLOUD-MIGRATION-GUIDE.md`
- **PRDs**: `/docs/prd/wasmcloud/`
- **wasmCloud Docs**: https://wasmcloud.com/docs

---

## Version History

### v2.0.0 (Current) - Consolidated Approach
- ✅ Single source of truth in values
- ✅ Loop-based ConfigMap generation
- ✅ Automatic WADM manifest generation
- ✅ Automatic capability linking
- ✅ 90% code reduction

### v1.0.0 (Deprecated) - Individual ConfigMaps
- ❌ 10+ separate ConfigMap files
- ❌ Manual WADM configuration
- ❌ Copy-paste maintenance
- ❌ Difficult to add new actors

---

## License

Copyright © 2024 Ekko Platform
