#!/bin/bash
set -e

# Push Ekko actors to OCI registry
# This script pushes wasmCloud actors as OCI artifacts to any OCI-compliant registry
# Supports: localhost docker-compose, GitLab Container Registry, Docker Hub, etc.

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# wasmCloud CLI (`wash`) writes state under $HOME. In sandboxed environments this may be blocked,
# so default to a repo-local home (also useful for reproducible pushes).
WASH_HOME="${WASH_HOME:-${SCRIPT_DIR}/.wash-home}"
mkdir -p "${WASH_HOME}"

wash_cmd() {
    HOME="${WASH_HOME}" wash "$@"
}

# Registry configuration
REGISTRY="${ACTOR_REGISTRY:-localhost:5001}"
PUSH_REGISTRY="${REGISTRY}"
REGISTRY_TYPE="${ACTOR_REGISTRY_TYPE:-local}"  # local, gitlab, dockerhub, generic
TAG="${ACTOR_TAG:-v1.0.0}"
ACTORS_DIR="target/wasm32-wasip1/release"

# Authentication (for remote registries)
REGISTRY_USERNAME="${REGISTRY_USERNAME:-}"
REGISTRY_PASSWORD="${REGISTRY_PASSWORD:-}"
CI_REGISTRY_IMAGE="${CI_REGISTRY_IMAGE:-}"  # GitLab CI variable

# All actors for deployment
ACTORS=(
  "health-check"
  "eth-raw-transactions"
  "evm-logs-ingestion"
  "eth-process-transactions"
  "eth-transfers-processor"
  "eth-contract-creation-processor"
  "eth-contract-transaction-processor"
  "btc-raw-transactions"
  "sol-raw-transactions"
  "alerts-processor"
  "transaction-processor"
  "notification-router"
  "abi-decoder"
  "transaction-ducklake-writer"
)

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# ============================================================================
# Registry Type Detection and Configuration
# ============================================================================

detect_registry_type() {
    if [[ "$REGISTRY" == "localhost:"* ]] || [[ "$REGISTRY" == "127.0.0.1:"* ]] || [[ "$REGISTRY" == "host.docker.internal:"* ]]; then
        REGISTRY_TYPE="local"
    elif [[ "$REGISTRY" == *"gitlab.com"* ]] || [[ -n "$CI_REGISTRY_IMAGE" ]]; then
        REGISTRY_TYPE="gitlab"
    elif [[ "$REGISTRY" == *"docker.io"* ]] || [[ "$REGISTRY" == "index.docker.io"* ]]; then
        REGISTRY_TYPE="dockerhub"
    else
        REGISTRY_TYPE="generic"
    fi
}

# Auto-detect if not explicitly set
if [ "$REGISTRY_TYPE" == "local" ] && [[ "$REGISTRY" != "localhost:"* ]]; then
    detect_registry_type
fi

if [[ "$REGISTRY" == "host.docker.internal:"* ]]; then
    PUSH_REGISTRY="localhost:${REGISTRY#host.docker.internal:}"
fi

# ============================================================================
# Registry Authentication
# ============================================================================

authenticate_registry() {
    case "$REGISTRY_TYPE" in
        local)
            log_info "Local registry - no authentication required"
            INSECURE_FLAG="--insecure"
            ;;
        gitlab)
            log_info "Authenticating with GitLab Container Registry..."
            if [ -n "$CI_REGISTRY_PASSWORD" ] && [ -n "$CI_REGISTRY_USER" ]; then
                # CI environment
                echo "$CI_REGISTRY_PASSWORD" | docker login -u "$CI_REGISTRY_USER" --password-stdin "$CI_REGISTRY" 2>/dev/null
                log_success "Authenticated using CI credentials"
            elif [ -n "$REGISTRY_PASSWORD" ] && [ -n "$REGISTRY_USERNAME" ]; then
                # Manual credentials
                echo "$REGISTRY_PASSWORD" | docker login -u "$REGISTRY_USERNAME" --password-stdin "$REGISTRY" 2>/dev/null
                log_success "Authenticated using provided credentials"
            else
                log_warning "No credentials provided - using cached Docker credentials"
            fi
            INSECURE_FLAG=""
            ;;
        dockerhub)
            log_info "Authenticating with Docker Hub..."
            if [ -n "$REGISTRY_PASSWORD" ] && [ -n "$REGISTRY_USERNAME" ]; then
                echo "$REGISTRY_PASSWORD" | docker login -u "$REGISTRY_USERNAME" --password-stdin 2>/dev/null
                log_success "Authenticated with Docker Hub"
            else
                log_warning "No credentials provided - using cached Docker credentials"
            fi
            INSECURE_FLAG=""
            ;;
        generic)
            log_info "Authenticating with registry: $REGISTRY"
            if [ -n "$REGISTRY_PASSWORD" ] && [ -n "$REGISTRY_USERNAME" ]; then
                echo "$REGISTRY_PASSWORD" | docker login -u "$REGISTRY_USERNAME" --password-stdin "$REGISTRY" 2>/dev/null
                log_success "Authenticated with registry"
            else
                log_warning "No credentials provided - assuming public registry or cached credentials"
            fi
            INSECURE_FLAG=""
            ;;
    esac
}

# ============================================================================
# Registry Connectivity Check
# ============================================================================

check_registry_connectivity() {
    log_info "Checking registry connectivity: $PUSH_REGISTRY"

    case "$REGISTRY_TYPE" in
        local)
            # For local registry, check HTTP endpoint
            if curl -sf "http://${PUSH_REGISTRY}/v2/" > /dev/null 2>&1; then
                log_success "Registry is accessible"
                return 0
            else
                log_error "Registry not accessible at http://${PUSH_REGISTRY}/v2/"
                log_info "Make sure docker-compose registry is running: docker-compose up -d registry"
                return 1
            fi
            ;;
        *)
            # For remote registries, assume accessible if authentication succeeded
            log_success "Registry connectivity assumed (authenticated successfully)"
            return 0
            ;;
    esac
}

# ============================================================================
# Build Full Image Reference
# ============================================================================

build_image_reference() {
    local actor_name=$1

    # Convert underscore to hyphen for image name
    local image_name=$(echo "$actor_name" | tr '_' '-')

    case "$REGISTRY_TYPE" in
        gitlab)
            # GitLab: registry.gitlab.com/group/project/wasmcloud/actor:tag
            if [ -n "$CI_REGISTRY_IMAGE" ]; then
                echo "${CI_REGISTRY_IMAGE}/wasmcloud/${image_name}:${TAG}"
            else
                echo "${REGISTRY}/wasmcloud/${image_name}:${TAG}"
            fi
            ;;
        dockerhub)
            # Docker Hub: username/actor:tag
            echo "${PUSH_REGISTRY}/${image_name}:${TAG}"
            ;;
        *)
            # Generic or local: registry/actor:tag
            echo "${PUSH_REGISTRY}/${image_name}:${TAG}"
            ;;
    esac
}

resolve_wasm_name() {
    local actor_name=$1

    echo "${actor_name//-/_}"
}

# ============================================================================
# Main Script
# ============================================================================

echo ""
echo "🚀 Ekko wasmCloud Actor Registry Push"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Configuration:"
echo "  Registry:      $REGISTRY"
if [ "$PUSH_REGISTRY" != "$REGISTRY" ]; then
    echo "  Push Registry: $PUSH_REGISTRY"
fi
echo "  Type:          $REGISTRY_TYPE"
echo "  Tag:           $TAG"
echo "  Actors:        ${#ACTORS[@]} actors"
echo ""

# Authenticate with registry
authenticate_registry

# Check registry connectivity
if ! check_registry_connectivity; then
    exit 1
fi

echo ""
log_info "Pushing actors to registry..."
echo ""

# Push each actor
SUCCESSFUL=0
FAILED=0

for actor in "${ACTORS[@]}"; do
  wasm_name=$(resolve_wasm_name "$actor")
  wasm_file="${ACTORS_DIR}/${wasm_name}.wasm"

  if [ ! -f "$wasm_file" ]; then
    log_error "Actor not found: $wasm_file"
    log_info "Run ./build.sh first to build actors"
    ((FAILED++))
    continue
  fi

  # Build full image reference
  registry_url=$(build_image_reference "$actor")

  echo "📦 Pushing: $actor"
  echo "   Source: $wasm_file"
  echo "   Target: $registry_url"

  # Use wash to push actor as OCI artifact
  if wash_cmd push "$registry_url" "$wasm_file" $INSECURE_FLAG --allow-latest 2>/dev/null; then
    log_success "Success"
    ((SUCCESSFUL++))
  else
    log_warning "Failed with wash - trying fallback method"
    # Fallback: use wash without --allow-latest
    if wash_cmd push "$registry_url" "$wasm_file" $INSECURE_FLAG 2>/dev/null; then
      log_success "Success (fallback)"
      ((SUCCESSFUL++))
    else
      log_error "Both methods failed for $actor"
      ((FAILED++))
    fi
  fi

  echo ""
done

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Push Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_success "$SUCCESSFUL actors pushed successfully"
if [ $FAILED -gt 0 ]; then
    log_error "$FAILED actors failed to push"
fi
echo ""

# List registry contents (for local registry only)
if [ "$REGISTRY_TYPE" == "local" ]; then
    echo "Registry catalog:"
    if curl -sf "http://${PUSH_REGISTRY}/v2/_catalog" > /dev/null 2>&1; then
        curl -s "http://${PUSH_REGISTRY}/v2/_catalog" | python3 -m json.tool 2>/dev/null || echo "  (catalog not available)"
    else
        echo "  (catalog not accessible)"
    fi
    echo ""
fi

# Exit with error if any actors failed
if [ $FAILED -gt 0 ]; then
    exit 1
fi

log_success "All actors pushed successfully!"
echo ""
