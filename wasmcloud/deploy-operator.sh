#!/bin/bash
set -euo pipefail

echo "🚀 WasmCloud Operator Deployment Script"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE=${NAMESPACE:-ekko}
WASMCLOUD_VERSION=${WASMCLOUD_VERSION:-latest}
WADM_VERSION=${WADM_VERSION:-latest}

echo -e "${BLUE}Configuration:${NC}"
echo "  Namespace: ${NAMESPACE}"
echo "  WasmCloud Version: ${WASMCLOUD_VERSION}"
echo "  WADM Version: ${WADM_VERSION}"
echo ""

# Prerequisites check
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

# Check Helm
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ Helm not found. Please install Helm first.${NC}"
    exit 1
fi

# Check wash CLI
if ! command -v wash &> /dev/null; then
    echo -e "${YELLOW}⚠️  wash CLI not found. Installing...${NC}"
    curl -s https://packagecloud.io/install/repositories/wasmcloud/core/script.bash.sh | sudo bash
    sudo apt-get install -y wash || brew install wasmcloud/tap/wash
fi

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster. Please check your kubeconfig.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# Step 1: Create namespace if it doesn't exist
echo -e "${YELLOW}Step 1: Ensuring namespace exists...${NC}"
kubectl create namespace ${NAMESPACE} 2>/dev/null || echo "  Namespace ${NAMESPACE} already exists"

# Step 2: Deploy WasmCloud Operator
echo -e "${YELLOW}Step 2: Deploying WasmCloud Operator...${NC}"

# Check if operator already exists
if kubectl get deployment -n wasmcloud-operator wasmcloud-operator &> /dev/null; then
    echo "  WasmCloud operator already deployed"
else
    echo "  Installing WasmCloud operator..."
    kubectl apply -k https://github.com/wasmCloud/wasmcloud-operator/deploy/base

    # Wait for operator to be ready
    echo "  Waiting for operator to be ready..."
    kubectl wait --for=condition=available --timeout=600s \
        deployment/wasmcloud-operator -n wasmcloud-operator || {
        echo -e "${RED}❌ Failed to deploy operator${NC}"
        exit 1
    }
fi

# Step 3: Verify CRDs are installed
echo -e "${YELLOW}Step 3: Verifying CRDs...${NC}"
for crd in wasmcloudhostconfigs.k8s.wasmcloud.dev; do
    if kubectl get crd $crd &> /dev/null; then
        echo -e "  ✅ CRD $crd found"
    else
        echo -e "${RED}  ❌ CRD $crd not found${NC}"
        exit 1
    fi
done

# Step 4: Check if NATS is already installed
echo -e "${YELLOW}Step 4: Checking NATS installation...${NC}"
if kubectl get service -n ${NAMESPACE} nats &> /dev/null; then
    echo "  NATS already installed in namespace ${NAMESPACE}"
    NATS_URL="nats.${NAMESPACE}.svc.cluster.local"
else
    echo "  Installing NATS with JetStream..."
    helm repo add nats https://nats-io.github.io/k8s/helm/charts/
    helm repo update

    # Install NATS with JetStream enabled
    helm install nats nats/nats -n ${NAMESPACE} \
        --set config.jetstream.enabled=true \
        --set config.jetstream.fileStore.enabled=true \
        --set cluster.enabled=false \
        --set auth.enabled=false \
        --wait

    NATS_URL="nats.${NAMESPACE}.svc.cluster.local"
fi

# Step 5: Install WADM
echo -e "${YELLOW}Step 5: Installing WADM...${NC}"
if helm list -n ${NAMESPACE} | grep -q wadm; then
    echo "  WADM already installed"
else
    echo "  Installing WADM via Helm..."

    # Create wadm-values.yaml with proper structure
    cat > /tmp/wadm-values.yaml <<EOF
wadm:
  image:
    repository: ghcr.io/wasmcloud/wadm
    tag: ${WADM_VERSION}
  config:
    nats:
      server: ${NATS_URL}:4222
      jetstream:
        enabled: true
EOF

    # Install WADM
    helm install wadm -n ${NAMESPACE} \
        -f /tmp/wadm-values.yaml \
        oci://ghcr.io/wasmcloud/charts/wadm \
        --version 0.2.10 \
        --wait || {
        echo -e "${RED}❌ Failed to install WADM${NC}"
        exit 1
    }
fi

# Step 6: Verify WADM is running
echo -e "${YELLOW}Step 6: Verifying WADM deployment...${NC}"
kubectl wait --for=condition=available --timeout=300s \
    deployment -l app.kubernetes.io/name=wadm -n ${NAMESPACE} || {
    echo -e "${YELLOW}⚠️  WADM deployment not ready, checking pods...${NC}"
    kubectl get pods -n ${NAMESPACE} -l app.kubernetes.io/name=wadm
}

# Step 7: Check Redis installation (required for state management)
echo -e "${YELLOW}Step 7: Checking Redis installation...${NC}"
if kubectl get service -n ${NAMESPACE} redis-master &> /dev/null; then
    echo "  Redis already installed in namespace ${NAMESPACE}"
else
    echo "  Installing Redis..."
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo update

    helm install redis bitnami/redis -n ${NAMESPACE} \
        --set auth.enabled=true \
        --set auth.password=redis123 \
        --set master.persistence.enabled=false \
        --wait
fi

# Step 8: Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ WasmCloud Operator Deployment Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Deployed components:"
echo "  ✅ WasmCloud Operator"
echo "  ✅ Custom Resource Definitions (CRDs)"
echo "  ✅ NATS with JetStream"
echo "  ✅ WADM (Application Deployment Manager)"
echo "  ✅ Redis (State Store)"
echo ""
echo "Next steps:"
echo "  1. Apply WasmCloudHostConfig: kubectl apply -f wasmcloud-host-config.yaml"
echo "  2. Deploy actors using WADM: kubectl apply -f ekko-actors.wadm.yaml"
echo "  3. Verify deployment: wash app get ekko-actors"
echo ""
echo "Useful commands:"
echo "  View operator logs: kubectl logs -n wasmcloud-operator -l app.kubernetes.io/name=wasmcloud-operator"
echo "  View WADM logs: kubectl logs -n ${NAMESPACE} -l app.kubernetes.io/name=wadm"
echo "  Check WasmCloud hosts: wash get hosts"
echo "  Check deployed apps: wash app list"