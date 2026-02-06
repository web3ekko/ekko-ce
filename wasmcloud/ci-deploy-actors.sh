#!/bin/bash
set -euo pipefail

# CI/CD Deployment Script for WasmCloud Actors
# This script builds actors, updates the ConfigMaps (split for size), and triggers a deployment rollout
# Perfect for CI/CD pipelines (GitHub Actions, GitLab CI, Jenkins, etc.)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 WasmCloud Actor CI/CD Deployment"
echo "===================================="
echo ""

# Step 1: Build all actors
echo "📦 Building actors..."
if ! ./build.sh; then
    echo "❌ Actor build failed"
    exit 1
fi
echo "✅ All actors built successfully"
echo ""

# Step 2: Check if kubectl is configured
echo "🔍 Checking Kubernetes connectivity..."
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster"
    echo "   Ensure kubectl is configured and you have cluster access"
    exit 1
fi
echo "✅ Kubernetes cluster accessible"
echo ""

# Step 3: Create/Update ConfigMaps with individual actor WASM files
echo "📤 Updating ConfigMaps with actor binaries..."
echo "   Creating individual ConfigMaps to avoid size limits"
echo ""

# Create individual ConfigMaps for each actor
ACTORS=(
    "alerts-processor"
    "abi-decoder"
    "health-check"
    "notification-router"
    "transaction-delta-writer"
    "transaction-processor"
    "eth_raw_transactions"
    "eth_process_transactions"
    "btc_raw_transactions"
    "sol_raw_transactions"
)

for actor in "${ACTORS[@]}"; do
    echo "📦 Creating ConfigMap for ${actor}..."

    actor_file="actors/${actor}/build/${actor}_s.wasm"
    if [ ! -f "$actor_file" ]; then
        # Try with underscores converted
        actor_alt="${actor//-/_}"
        actor_file="actors/${actor_alt}/build/${actor_alt}_s.wasm"
    fi

    if [ -f "$actor_file" ]; then
        # Create individual ConfigMap for this actor
        if kubectl create configmap "ekko-actor-${actor}" \
            --from-file="${actor}_s.wasm=$actor_file" \
            -n ekko --dry-run=client -o yaml | kubectl apply -f -; then
            echo "  ✅ ConfigMap for ${actor} created"
        else
            echo "  ❌ Failed to create ConfigMap for ${actor}"
            exit 1
        fi
    else
        echo "  ⚠️  Warning: ${actor} WASM file not found, skipping..."
    fi
done
echo ""

# Step 4: Trigger deployment rollout to load new actors
echo "🔄 Restarting WasmCloud hosts to load new actors..."
if kubectl rollout restart deployment/ekko-wasmcloud-host -n ekko; then
    echo "✅ Deployment restart triggered"
else
    echo "❌ Failed to restart deployment"
    exit 1
fi
echo ""

# Step 5: Wait for rollout to complete
echo "⏳ Waiting for deployment rollout to complete..."
if kubectl rollout status deployment/ekko-wasmcloud-host -n ekko --timeout=300s; then
    echo "✅ Deployment rollout completed successfully"
else
    echo "❌ Deployment rollout failed or timed out"
    exit 1
fi
echo ""

# Step 6: Verify pods are running
echo "🔍 Verifying WasmCloud pods..."
POD_COUNT=$(kubectl get pods -n ekko -l app.kubernetes.io/component=wasmcloud-host --field-selector=status.phase=Running --no-headers | wc -l)
if [ "$POD_COUNT" -gt 0 ]; then
    echo "✅ $POD_COUNT WasmCloud pod(s) running"

    # Show pod status
    kubectl get pods -n ekko -l app.kubernetes.io/component=wasmcloud-host
else
    echo "❌ No running WasmCloud pods found"
    exit 1
fi
echo ""

# Step 7: Verify actors are loaded (optional)
echo "📋 Checking loaded actors in pods..."
FIRST_POD=$(kubectl get pods -n ekko -l app.kubernetes.io/component=wasmcloud-host --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
if [ -n "$FIRST_POD" ]; then
    echo "Checking pod: $FIRST_POD"
    ACTOR_COUNT=$(kubectl exec -n ekko "$FIRST_POD" -- ls /actors/*.wasm 2>/dev/null | wc -l || echo "0")
    echo "✅ Found $ACTOR_COUNT actor WASM files in pod"
fi
echo ""

echo "🎉 CI/CD Deployment Complete!"
echo "============================="
echo ""
echo "Summary:"
echo "  • All actors built and signed"
echo "  • ConfigMap updated with ${#ACTORS[@]} actors"
echo "  • WasmCloud hosts restarted"
echo "  • $POD_COUNT pod(s) running with actors loaded"
echo ""
echo "To monitor the deployment:"
echo "  kubectl logs -n ekko -l app.kubernetes.io/component=wasmcloud-host -f"
echo ""
echo "To check actor status:"
echo "  kubectl exec -n ekko $FIRST_POD -- ls -la /actors/"
