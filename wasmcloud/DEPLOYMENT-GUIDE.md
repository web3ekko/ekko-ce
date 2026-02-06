# WasmCloud Deployment Guide

Complete deployment guide for Ekko's wasmCloud platform covering both automated CI/CD and manual deployment.

---

## Table of Contents

1. [Overview](#overview)
2. [CI/CD Deployment (Production)](#cicd-deployment-production)
3. [Orbstack Local Deployment (Automated)](#orbstack-local-deployment-automated)
4. [Manual Deployment (Development)](#manual-deployment-development)
5. [Verification](#verification)
6. [Monitoring & Operations](#monitoring--operations)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### Deployment Options

This guide covers **three deployment approaches**:

1. **CI/CD Deployment (Production)** - Automated GitLab pipeline for production
2. **Orbstack Local Deployment** - One-command automated local development (Recommended)
3. **Manual Deployment** - Step-by-step deployment for learning/debugging

### Deployment Architecture

**Production CI/CD Pipeline**:
```
┌─────────────────────────────────────────┐
│ GitLab CI/CD Pipeline                   │
├─────────────────────────────────────────┤
│ 1. Build Stage:                         │
│    - Compile actors to WASM             │
│    - Push to GitLab Container Registry  │
├─────────────────────────────────────────┤
│ 2. Deploy Stage:                        │
│    - Deploy official Helm chart         │
│    - Generate manifest from template    │
│    - Deploy actors via WADM             │
├─────────────────────────────────────────┤
│ 3. Verification Stage:                  │
│    - Validate all actors deployed       │
│    - Verify all providers healthy       │
│    - Check version matches              │
└─────────────────────────────────────────┘
```

**Orbstack Local Deployment**:
```
┌─────────────────────────────────────────┐
│ Automated Local Development             │
├─────────────────────────────────────────┤
│ 1. Infrastructure:                      │
│    - Redis, PostgreSQL (Helm)           │
│    - NATS (wasmCloud chart)             │
├─────────────────────────────────────────┤
│ 2. Ekko Services:                       │
│    - API (Django + NLP)                 │
│    - Dashboard (React)                  │
├─────────────────────────────────────────┤
│ 3. wasmCloud Platform:                  │
│    - Official Helm chart                │
│    - Local OCI registry                 │
│    - All blockchain actors              │
└─────────────────────────────────────────┘
```

**Technology Stack**:
- **wasmCloud Platform**: Official Helm chart v0.1.2
- **Actor Registry**: GitLab Container Registry (production) / Local registry (development)
- **Manifest System**: Template-based with variable substitution
- **Deployment Tool**: WADM (wasmCloud Application Deployment Manager)
- **Verification**: Automated manifest-driven validation

---

## CI/CD Deployment (Production)

### Prerequisites

**GitLab CI/CD Variables** (set in GitLab → Settings → CI/CD → Variables):
```bash
K8S_SERVER_URL            # Kubernetes API server URL
K8S_SERVICE_ACCOUNT_TOKEN # Service account token with deploy permissions
CI_REGISTRY               # GitLab Container Registry (auto-set)
CI_REGISTRY_USER          # Registry username (auto-set)
CI_REGISTRY_PASSWORD      # Registry password (auto-set)
```

### Pipeline Stages

#### Stage 1: Build & Push Actors

**Job**: `build-wasmcloud-actors`

```yaml
# Runs automatically on changes to apps/wasmcloud/**/*
# Image: rust:1.75
# Duration: ~3-5 minutes

Actions:
1. Install Rust wasm32-wasip1 target
2. Install wash CLI
3. Build all actors: ./build.sh
4. Push actors to GitLab Container Registry
5. Tag with commit SHA: ${CI_COMMIT_SHORT_SHA}
```

**Outputs**:
- WASM binaries: `apps/wasmcloud/target/wasm32-wasip1/release/*.wasm`
- OCI artifacts in GitLab Container Registry

#### Stage 2: Deploy Infrastructure & Actors

**Job**: `deploy-wasmcloud-production`

```yaml
# Manual trigger only (for safety)
# Image: alpine/helm:3.11.2
# Duration: ~5-8 minutes

Actions:
1. Deploy NATS + WADM + Operator (official Helm chart)
2. Enable wasmCloud hosts (3 replicas)
3. Generate manifest from template
4. Deploy actors via WADM
```

**Detailed Steps**:

**2.1: Deploy Infrastructure**
```bash
helm upgrade --install ekko-wasmcloud \
  oci://ghcr.io/wasmcloud/charts/wasmcloud-platform \
  --version 0.1.2 \
  --namespace ekko-production --create-namespace \
  --set nats.config.cluster.enabled=true \
  --set nats.config.cluster.replicas=3 \
  --set nats.config.jetstream.enabled=true \
  --set wadm.resources.limits.cpu=200m \
  --set wadm.resources.limits.memory=256Mi
```

**2.2: Enable wasmCloud Hosts**
```bash
helm upgrade ekko-wasmcloud \
  oci://ghcr.io/wasmcloud/charts/wasmcloud-platform \
  --version 0.1.2 \
  --namespace ekko-production \
  --reuse-values \
  --set "hostConfig.enabled=true" \
  --set "hostConfig.hostReplicas=3" \
  --set "hostConfig.lattice=ekko-prod" \
  --set "hostConfig.hostLabels.environment=production"
```

**2.3: Generate Manifest**
```bash
export ENVIRONMENT=production
export MANIFEST_VERSION=${CI_COMMIT_SHORT_SHA}
export ACTOR_TAG=${CI_COMMIT_SHORT_SHA}
./generate-manifest.sh

# Generates: manifests/ekko-actors-generated.yaml
# From template: manifests/ekko-actors.template.yaml
```

**2.4: Deploy Actors**
```bash
# Port-forward to WADM
kubectl port-forward -n ekko-production svc/wadm 4223:4223 &

# Store manifest
wash app put manifests/ekko-actors-generated.yaml

# Deploy application
wash app deploy ekko-platform ${CI_COMMIT_SHORT_SHA}
```

#### Stage 3: Verify Deployment

**Job**: `verify-wasmcloud-production`

```yaml
# Runs automatically after successful deployment
# Blocks pipeline on failure
# Duration: ~1-2 minutes

Actions:
1. Parse manifest to extract expected components
2. Query WADM for actual deployment state
3. Verify all actors are deployed and healthy
4. Verify all providers are deployed and healthy
5. Verify version matches commit SHA
```

**Verification Process**:
```bash
./verify-wadm-deployment.sh

# Checks:
✅ 13 actors deployed (from manifest)
✅ 3 providers deployed (from manifest)
✅ Version = CI_COMMIT_SHORT_SHA
✅ Application status = Deployed
```

**Exit Codes**:
- `0` = All verifications passed
- `1` = One or more verifications failed (pipeline fails)

### Manual Trigger

**To deploy to production**:

1. Navigate to GitLab → CI/CD → Pipelines
2. Find pipeline for commit you want to deploy
3. Click on `deploy-wasmcloud-production` job
4. Click "Play" button to trigger

**What happens**:
- Build job must have succeeded
- Deploy job runs through all stages
- Verification runs automatically
- Pipeline succeeds only if all checks pass

### Environment Variables

**Generated by CI**:
```bash
CI_COMMIT_SHORT_SHA      # Used for versioning (e.g., "a1b2c3d")
CI_REGISTRY_IMAGE        # Base registry path
NAMESPACE=ekko-production
LATTICE=ekko-prod
```

**Actor Images**:
```
${CI_REGISTRY_IMAGE}/wasmcloud/health-check:${CI_COMMIT_SHORT_SHA}
${CI_REGISTRY_IMAGE}/wasmcloud/eth-raw-transactions:${CI_COMMIT_SHORT_SHA}
${CI_REGISTRY_IMAGE}/wasmcloud/alert-processor:${CI_COMMIT_SHORT_SHA}
... (13 total actors)
```

---

## Orbstack Local Deployment (Automated)

**Recommended for local development** - Deploys entire Ekko platform (API, Dashboard, wasmCloud) in one command.

### Prerequisites

**Required Tools**:
```bash
# OrbStack (includes Docker and Kubernetes)
brew install orbstack

# Helm
brew install helm

# wash CLI (wasmCloud Shell)
brew install wasmcloud/wasmcloud/wash

# kubectl (included with OrbStack, but verify)
brew install kubectl
```

**OrbStack Setup**:
```bash
# Start OrbStack Kubernetes
orb start k8s

# Verify it's running
kubectl config use-context orbstack
kubectl get nodes
```

### One-Command Deployment

**Deploy everything**:
```bash
# From project root
./scripts/deployment/deploy .env.orbstack
```

### What Gets Deployed

**Infrastructure (Step 4)**:
- ✅ Redis (Bitnami Helm chart)
- ✅ PostgreSQL (Bitnami Helm chart)
- ✅ NATS (deployed with wasmCloud platform)

**wasmCloud Platform (Step 6)**:
- ✅ Official wasmCloud Helm chart v0.1.2
- ✅ NATS + WADM + Operator
- ✅ wasmCloud hosts (1 replica for local dev)
- ✅ Configured for development lattice: `ekko-dev`

**Ekko Services (Step 8)**:
- ✅ **API** - Django backend with NLP (`ekko-api`)
- ✅ **Dashboard** - React frontend (`ekko-dashboard`)

**wasmCloud Actors (Step 9)**:
- ✅ Local OCI registry (host.docker.internal:5001)
- ✅ All 13 blockchain processing actors
- ✅ Deployed via WADM

### Deployment Steps (Automated)

**Step 1: Prerequisites Check**
- Verifies OrbStack, kubectl, helm, docker installed
- Checks for wash CLI (optional but recommended)

**Step 2: OrbStack Kubernetes Setup**
- Starts OrbStack Kubernetes if not running
- Configures kubectl context to `orbstack`

**Step 3: Namespace Creation**
- Creates `ekko` namespace

**Step 4: Infrastructure Deployment**
```bash
# Redis
helm upgrade --install redis bitnami/redis \
  --namespace ekko \
  --set auth.password=redis123

# PostgreSQL
helm upgrade --install postgresql bitnami/postgresql \
  --namespace ekko \
  --set auth.username=ekko \
  --set auth.password=ekko123 \
  --set auth.database=ekko
```

**Step 5: Official wasmCloud Chart**
```bash
# Pull chart dependencies
helm dependency update apps/wasmcloud/chart

# Deploy infrastructure (NATS, WADM, Operator)
helm upgrade --install ekko-wasmcloud \
  oci://ghcr.io/wasmcloud/charts/wasmcloud-platform \
  --namespace ekko \
  --set nats.config.jetstream.enabled=true \
  --set wadm.resources.limits.cpu=100m \
  --set wadm.resources.limits.memory=128Mi

# Enable wasmCloud hosts
helm upgrade ekko-wasmcloud \
  oci://ghcr.io/wasmcloud/charts/wasmcloud-platform \
  --namespace ekko \
  --reuse-values \
  --set "hostConfig.enabled=true" \
  --set "hostConfig.lattice=ekko-dev" \
  --set "hostConfig.hostLabels.environment=development"
```

**Step 6: Local Actor Registry**
```bash
# Start docker-compose registry
docker-compose up -d registry

# Verify accessible
curl http://localhost:5001/v2/
```

**Step 7: Build and Push Actors**
```bash
cd apps/wasmcloud

# Build all WASM actors
./build.sh

# Push to local registry
export ACTOR_REGISTRY=host.docker.internal:5001
export ACTOR_TAG=v1.0.0
./push-actors-to-registry.sh
```

**Step 8: Build Ekko Services**
```bash
# Build API
docker build -t ekko-api:latest -f apps/api/Dockerfile apps/api/

# Build Dashboard
docker build --target production -t ekko-dashboard:latest \
  -f apps/dashboard/Dockerfile apps/dashboard/

```

**Step 9: Deploy Ekko Services via Helm**
```bash
# Deploy API
helm upgrade --install ekko-api apps/api/chart \
  --namespace ekko \
  --values apps/api/chart/values.yaml

# Deploy Dashboard
helm upgrade --install ekko-dashboard apps/dashboard/chart \
  --namespace ekko \
  --values apps/dashboard/chart/values.yaml

```

**Step 10: Deploy Actors via WADM**
```bash
# Port-forward to NATS
kubectl port-forward -n ekko svc/nats 4222:4222 4223:4223 &

# Set environment
export WASMCLOUD_LATTICE=ekko-dev
export ENVIRONMENT=development
export MANIFEST_VERSION=v1.0.0
export ACTOR_REGISTRY=host.docker.internal:5001
export ACTOR_TAG=v1.0.0

# Generate manifest
./generate-manifest.sh

# Deploy via WADM
wash app put manifests/ekko-actors-generated.yaml
wash app deploy ekko-platform v1.0.0
```

### Accessing Services

**After successful deployment**:

```bash
# Get service URLs
echo "Dashboard: http://localhost:$(kubectl get svc ekko-dashboard -n ekko -o jsonpath='{.spec.ports[0].nodePort}')"
echo "API:       http://localhost:$(kubectl get svc ekko-api -n ekko -o jsonpath='{.spec.ports[0].nodePort}')"
```

**Default NodePorts** (usually):
- Dashboard: http://localhost:30000
- API: http://localhost:30001

### Idempotency

The script is **fully idempotent**:
- ✅ Safe to run multiple times
- ✅ Checks if services already deployed
- ✅ Skips healthy components
- ✅ Redeploys unhealthy components
- ✅ Updates actors if code changed

**Rerun anytime**:
```bash
./scripts/deployment/deploy .env.orbstack
```

### Health Checks

**Built-in health monitoring**:
```bash
# Check pod status
kubectl get pods -n ekko

# Check wasmCloud status
kubectl port-forward -n ekko svc/nats 4222:4222 4223:4223 &
wash get hosts
wash get inventory
wash app list
```

### Environment Configuration

**Development environment** (`.env.development`):
```bash
ENVIRONMENT=development
ACTOR_REGISTRY=host.docker.internal:5001
ACTOR_TAG=v1.0.0
MANIFEST_VERSION=v1.0.0
WASMCLOUD_LATTICE=ekko-dev
```

### Cleanup

**Remove all deployments**:
```bash
# Delete namespace (removes everything)
kubectl delete namespace ekko

# Stop local registry
docker-compose down registry

# Stop OrbStack Kubernetes
orb stop k8s
```

### Troubleshooting

**wasmCloud hosts not starting**:
- Large image, first pull takes 5-10 minutes
- Check: `kubectl logs -n ekko -l app.kubernetes.io/name=wasmcloud-host`

**Registry not accessible**:
```bash
# Restart registry
docker-compose restart registry

# Test connectivity
curl http://localhost:5001/v2/
```

**Actors not deploying**:
```bash
# Check WADM is ready
kubectl get pods -n ekko -l app.kubernetes.io/name=wadm

# Check logs
kubectl logs -n ekko -l app.kubernetes.io/name=wadm
```

**Port-forward issues**:
```bash
# Kill existing port-forwards
pkill -f "kubectl port-forward"

# Restart
kubectl port-forward -n ekko svc/nats 4222:4222 4223:4223 &
```

### Development Workflow

**Typical iteration cycle**:

1. **Make code changes** to actors
2. **Rebuild**:
   ```bash
   cd apps/wasmcloud
   ./build.sh
   ```
3. **Push to registry**:
   ```bash
   export ACTOR_REGISTRY=host.docker.internal:5001
   export ACTOR_TAG=v1.0.0
   ./push-actors-to-registry.sh
   ```
4. **Redeploy**:
   ```bash
   ./generate-manifest.sh
   wash app put manifests/ekko-actors-generated.yaml
   wash app deploy ekko-platform v1.0.0
   ```

**Or use unified script**:
```bash
SKIP_BUILD=true ./scripts/deployment/deploy .env.orbstack
```

---

## Manual Deployment (Development)

### Prerequisites

**Required Tools**:
```bash
# Rust toolchain
rustup target add wasm32-wasip1

# wash CLI (wasmCloud Shell)
# macOS
brew install wasmcloud/wasmcloud/wash

# Linux/Others
cargo install wash-cli

# kubectl (for Kubernetes deployments)
brew install kubectl

# Helm (for infrastructure deployment)
brew install helm
```

**Infrastructure Requirements**:
- Kubernetes cluster (OrbStack, K3s, or cloud)
- NATS with JetStream enabled
- Redis instance
- OCI registry (local or remote)

### Option A: Automated Deployment

**Using scripts/deployment/deploy** (Recommended):

```bash
# Deploy to OrbStack
./scripts/deployment/deploy .env.orbstack

# Preview changes without deploying
DRY_RUN=true ./scripts/deployment/deploy .env.orbstack

# Skip phases
SKIP_BUILD=true ./scripts/deployment/deploy .env.orbstack      # Skip build
./scripts/deployment/deploy .env.orbstack --skip-applications  # Skip API/dashboard
./scripts/deployment/deploy .env.orbstack --skip-actors        # Skip wasmCloud actors/providers
```

**What it does**:
1. Loads and validates the environment file
2. Builds images/artifacts (unless `SKIP_BUILD=true`)
3. Deploys infrastructure (Kubernetes + Helm)
4. Deploys wasmCloud actors/providers (unless `--skip-actors`)
5. Deploys API/dashboard apps (unless `--skip-applications`)

**Environment Files**:
- `.env.orbstack` - Local OrbStack settings
- `.env.development` - Development settings
- `.env.production` - Production settings

### Option B: Manual Step-by-Step

**Step 1: Build Actors**

```bash
cd apps/wasmcloud

# Build all actors to WASM
./build.sh
```

Expected output:
```
Building all WasmCloud actors...
Compiling actors to WASM...
   Compiling health-check v0.1.0
   Compiling eth-raw-transactions v0.1.0
   ... (13 actors total)
    Finished `release` profile [optimized] target(s) in 45.2s

✅ All actors built successfully
```

**Step 2: Setup Local Registry** (Development only)

```bash
# Start local OCI registry
docker run -d -p 5001:5001 --restart=always --name registry registry:2

# Verify it's running
curl http://localhost:5001/v2/_catalog
```

**Step 3: Push Actors to Registry**

```bash
# Set environment
export ACTOR_REGISTRY=localhost:5001
export ACTOR_TAG=v1.0.0

# Push all actors
./push-actors-to-registry.sh
```

**Step 4: Deploy Infrastructure** (if not already deployed)

```bash
# Add wasmCloud Helm repo
helm repo add wasmcloud https://wasmcloud.github.io/charts
helm repo update

# Deploy platform
helm upgrade --install ekko-wasmcloud \
  oci://ghcr.io/wasmcloud/charts/wasmcloud-platform \
  --version 0.1.2 \
  --namespace ekko --create-namespace \
  --set nats.config.cluster.enabled=true \
  --set nats.config.jetstream.enabled=true \
  --set wadm.resources.limits.cpu=200m \
  --set wadm.resources.limits.memory=256Mi

# Enable hosts
helm upgrade ekko-wasmcloud \
  oci://ghcr.io/wasmcloud/charts/wasmcloud-platform \
  --version 0.1.2 \
  --namespace ekko \
  --reuse-values \
  --set "hostConfig.enabled=true" \
  --set "hostConfig.hostReplicas=1" \
  --set "hostConfig.lattice=default"
```

**Step 5: Generate Manifest**

```bash
# Set environment
export ENVIRONMENT=development
export MANIFEST_VERSION=v1.0.0
export ACTOR_REGISTRY=host.docker.internal:5001  # or localhost:5001
export ACTOR_TAG=v1.0.0

# Generate manifest
./generate-manifest.sh

# Verify generated file
cat manifests/ekko-actors-generated.yaml
```

**Step 6: Deploy Actors via WADM**

```bash
# Port-forward to WADM
kubectl port-forward -n ekko svc/wadm 4223:4223 &

# Set wash environment
export WASMCLOUD_LATTICE=default

# Store manifest
wash app put manifests/ekko-actors-generated.yaml

# Deploy application
wash app deploy ekko-platform v1.0.0

# Check status
wash app status ekko-platform
```

**Step 7: Verify Deployment**

```bash
# Set environment
export NAMESPACE=ekko
export LATTICE=default
export MANIFEST_FILE=manifests/ekko-actors-generated.yaml
export APPLICATION_NAME=ekko-platform
export EXPECTED_VERSION=v1.0.0

# Run verification
./verify-wadm-deployment.sh
```

---

## Verification

### Automated Verification

The `verify-wadm-deployment.sh` script validates deployment by:

**1. Parsing Manifest**
- Extracts all expected actors and providers
- Gets expected replica counts
- No hardcoded component lists

**2. Querying WADM**
- Gets actual deployment state via `wash app status`
- Compares expected vs actual components

**3. Component Verification**
```bash
For each actor in manifest:
  ✅ Actor exists in deployment
  ✅ Actor status is Deployed or Running
  ✅ Instance count matches manifest

For each provider in manifest:
  ✅ Provider exists in deployment
  ✅ Provider status is Deployed or Running
```

**4. Version Verification**
```bash
✅ Deployed version matches expected version
```

**Example Output**:
```
🔍 WADM Deployment Verification
========================================
Namespace:    ekko-production
Lattice:      ekko-prod
Application:  ekko-platform
Expected Ver: a1b2c3d

📋 Checking Prerequisites...
✅ wash CLI installed
✅ yq installed
✅ jq installed
✅ Manifest file found

📝 Parsing Manifest for Expected Components...
Expected Components:
  Actors:    13
  Providers: 3

🔍 Querying WADM Deployment Status...
✅ Application status retrieved

🏷️  Verifying Deployment Version...
✅ Version matches: a1b2c3d

🎯 Verifying Application Status...
✅ Application status: Deployed

🎭 Verifying Actors...
  ✅ health-check: Deployed
  ✅ eth-raw-transactions: Deployed
  ✅ alert-processor: Deployed
  ... (13 total)
✅ All 13 actors verified

🔌 Verifying Providers...
  ✅ nats-messaging: Deployed
  ✅ redis-keyvalue: Deployed
  ✅ http-client: Deployed
✅ All 3 providers verified

========================================
📊 Verification Summary
========================================
Application:  ekko-platform
Status:       Deployed
Version:      a1b2c3d

Components:
  Actors:     13 expected, 13 verified
  Providers:  3 expected, 3 verified

✅ VERIFICATION PASSED: All components healthy
```

### Manual Verification

**Check wasmCloud Hosts**:
```bash
wash get hosts

# Expected output:
Host ID                                                     Uptime (seconds)
NCPC372PCUVR2XA444LQHLUSWTNNHM3GTXHKESB5XOIQO2JIOXSLLU5T  300
```

**Check Application Status**:
```bash
wash app status ekko-platform

# Expected output:
Name: ekko-platform
Version: a1b2c3d
Status: Deployed
```

**Check Actor Inventory**:
```bash
wash get inventory

# Should show all 13 actors running
```

**Check Links**:
```bash
wash get links

# Should show NATS and Redis links for all actors
```

---

## Monitoring & Operations

### Health Monitoring

**Check Pod Status**:
```bash
kubectl get pods -n ekko-production

# All pods should be Running
NAME                                 READY   STATUS    RESTARTS   AGE
nats-0                              1/1     Running   0          10m
nats-1                              1/1     Running   0          10m
nats-2                              1/1     Running   0          10m
wadm-xxx                            1/1     Running   0          10m
wasmcloud-host-xxx                  1/1     Running   0          10m
```

**Monitor Actor Logs**:
```bash
# Watch wasmCloud host logs
kubectl logs -n ekko-production -l app.kubernetes.io/name=wasmcloud-host -f

# Filter for specific actor
kubectl logs -n ekko-production -l app.kubernetes.io/name=wasmcloud-host -f | grep eth-raw
```

**NATS Monitoring**:
```bash
# Install NATS CLI
brew install nats-io/nats-tools/nats

# Monitor message flow
nats stream ls
nats stream info ekko

# Subscribe to processed messages
nats sub "transfers.processed.evm"
nats sub "contracts.deployed.evm"
```

### Scaling Operations

**Scale wasmCloud Hosts**:
```bash
helm upgrade ekko-wasmcloud \
  oci://ghcr.io/wasmcloud/charts/wasmcloud-platform \
  --version 0.1.2 \
  --namespace ekko-production \
  --reuse-values \
  --set "hostConfig.hostReplicas=5"  # Scale to 5 hosts
```

**Scale Individual Actors** (edit manifest):
```yaml
# manifests/ekko-actors.template.yaml
- name: eth-transfers-processor
  traits:
    - type: spreadscaler
      properties:
        replicas: 4  # Increase from 2 to 4
```

Then redeploy:
```bash
./generate-manifest.sh
wash app put manifests/ekko-actors-generated.yaml
wash app deploy ekko-platform <new-version>
```

---

## Troubleshooting

### Deployment Failures

**Symptom**: `verify-wasmcloud-production` job fails

**Resolution**:
```bash
# 1. Check which components failed
#    Look at verification job output

# 2. Check wasmCloud host logs
kubectl logs -n ekko-production -l app.kubernetes.io/name=wasmcloud-host --tail=100

# 3. Check WADM logs
kubectl logs -n ekko-production -l app.kubernetes.io/component=wadm --tail=100

# 4. Manually check deployment
kubectl port-forward -n ekko-production svc/wadm 4223:4223 &
wash app status ekko-platform
```

**Common Issues**:
- **Image pull failures**: Check GitLab Container Registry authentication
- **Insufficient resources**: Scale down replica counts or increase node resources
- **NATS connectivity**: Verify NATS pods are running and healthy

### Actor Not Starting

**Symptom**: Actor shows in manifest but not in inventory

**Resolution**:
```bash
# 1. Check actor image is accessible
wash pull ${CI_REGISTRY_IMAGE}/wasmcloud/eth-raw-transactions:${TAG}

# 2. Check host resources
kubectl top pods -n ekko-production

# 3. Check for errors in host logs
kubectl logs -n ekko-production <wasmcloud-host-pod> | grep ERROR
```

### Version Mismatch

**Symptom**: Verification fails with version mismatch

**Resolution**:
```bash
# Check deployed version
wash app status ekko-platform

# Check expected version from CI
echo ${CI_COMMIT_SHORT_SHA}

# Redeploy with correct version
wash app deploy ekko-platform ${CI_COMMIT_SHORT_SHA}
```

### OCI Registry Issues

**Symptom**: Cannot pull actor images

**Resolution**:
```bash
# Test registry connectivity
curl -I https://${CI_REGISTRY}/v2/

# Check authentication
docker login ${CI_REGISTRY}

# Verify image exists
wash pull ${CI_REGISTRY_IMAGE}/wasmcloud/health-check:${TAG}
```

---

## Appendix

### Complete Command Reference

**Build**:
```bash
./build.sh
```

**Push**:
```bash
export ACTOR_REGISTRY=<registry>
export ACTOR_TAG=<tag>
./push-actors-to-registry.sh
```

**Generate Manifest**:
```bash
export ENVIRONMENT=<env>
export MANIFEST_VERSION=<version>
export ACTOR_REGISTRY=<registry>
export ACTOR_TAG=<tag>
./generate-manifest.sh
```

**Deploy**:
```bash
wash app put manifests/ekko-actors-generated.yaml
wash app deploy ekko-platform <version>
```

**Verify**:
```bash
export NAMESPACE=<namespace>
export LATTICE=<lattice>
export EXPECTED_VERSION=<version>
./verify-wadm-deployment.sh
```

### File Locations

- **Build Script**: `apps/wasmcloud/build.sh`
- **Push Script**: `apps/wasmcloud/push-actors-to-registry.sh`
- **Generate Script**: `apps/wasmcloud/generate-manifest.sh`
- **Verification Script**: `apps/wasmcloud/verify-wadm-deployment.sh`
- **Unified Deploy**: `scripts/deployment/deploy`
- **Manifest Template**: `apps/wasmcloud/manifests/ekko-actors.template.yaml`
- **Generated Manifest**: `apps/wasmcloud/manifests/ekko-actors-generated.yaml`
- **GitLab CI**: `.gitlab-ci.yml`

### Support

For issues or questions:
1. Check this guide
2. Review GitLab CI logs
3. Check wasmCloud docs: https://wasmcloud.com/docs
4. Contact: team@ekko.zone
