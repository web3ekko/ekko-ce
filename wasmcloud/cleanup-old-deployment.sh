#!/bin/bash
set -euo pipefail

echo "🧹 Cleaning up old WasmCloud deployment..."
echo "============================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

NAMESPACE=${NAMESPACE:-ekko}

echo -e "${YELLOW}Target namespace: ${NAMESPACE}${NC}"
echo ""

# Step 1: Uninstall custom Helm releases
echo -e "${YELLOW}Step 1: Uninstalling Helm releases...${NC}"
helm list -n ${NAMESPACE} | grep -E 'wasmcloud|wadm' | awk '{print $1}' | while read release; do
    if [ ! -z "$release" ]; then
        echo "  Uninstalling Helm release: $release"
        helm uninstall $release -n ${NAMESPACE} || true
    fi
done

# Step 2: Remove duplicate deployments
echo -e "${YELLOW}Step 2: Removing duplicate deployments...${NC}"
kubectl delete deployment -n ${NAMESPACE} \
  ekko-wasmcloud-wadm \
  wasmcloud-ekko-wasmcloud-wadm \
  wasmcloud-ekko-wasmcloud-host \
  ekko-wasmcloud-host \
  wasmcloud-ekko-wasmcloud-abi-decoder \
  wasmcloud-ekko-wasmcloud-eth-actor 2>/dev/null || true

# Step 3: Remove StatefulSets
echo -e "${YELLOW}Step 3: Removing StatefulSets...${NC}"
kubectl delete statefulset -n ${NAMESPACE} \
  ekko-wasmcloud-wadm \
  wasmcloud-ekko-wasmcloud-wadm 2>/dev/null || true

# Step 4: Remove Services
echo -e "${YELLOW}Step 4: Removing Services...${NC}"
kubectl delete service -n ${NAMESPACE} \
  ekko-wasmcloud-wadm \
  wasmcloud-ekko-wasmcloud-wadm \
  ekko-wasmcloud-host \
  wasmcloud-ekko-wasmcloud-host 2>/dev/null || true

# Step 5: Remove ConfigMaps related to WasmCloud
echo -e "${YELLOW}Step 5: Removing ConfigMaps...${NC}"
kubectl delete configmap -n ${NAMESPACE} \
  wasmcloud-actors \
  ekko-wasmcloud-actors \
  wasmcloud-config 2>/dev/null || true

# Step 6: Remove PVCs (if any)
echo -e "${YELLOW}Step 6: Removing PersistentVolumeClaims...${NC}"
kubectl delete pvc -n ${NAMESPACE} -l app.kubernetes.io/name=wasmcloud 2>/dev/null || true

# Step 7: Remove any Jobs
echo -e "${YELLOW}Step 7: Removing Jobs...${NC}"
kubectl delete job -n ${NAMESPACE} -l app.kubernetes.io/name=wasmcloud 2>/dev/null || true

# Step 8: Kill any hanging port-forwards
echo -e "${YELLOW}Step 8: Cleaning up port-forwards...${NC}"
for port in 4222 4223 4224 4225; do
    lsof -ti:$port 2>/dev/null | xargs kill -9 2>/dev/null || true
done

# Step 9: Wait for pods to terminate
echo -e "${YELLOW}Step 9: Waiting for pods to terminate...${NC}"
kubectl wait --for=delete pod -l app.kubernetes.io/name=wasmcloud -n ${NAMESPACE} --timeout=60s 2>/dev/null || true

# Step 10: Verify cleanup
echo -e "${YELLOW}Step 10: Verifying cleanup...${NC}"
echo ""
echo "Remaining WasmCloud resources:"
kubectl get all -n ${NAMESPACE} | grep -E 'wasmcloud|wadm' || echo "  None found ✅"

echo ""
echo -e "${GREEN}✅ Cleanup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Run './deploy-operator.sh' to install WasmCloud operator"
echo "  2. Apply WasmCloudHostConfig resources"
echo "  3. Deploy actors using WADM"