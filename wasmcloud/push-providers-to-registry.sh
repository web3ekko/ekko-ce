#!/bin/bash
set -e

# Push Ekko providers to OCI registry
# This script pushes wasmCloud providers as PAR (Provider Archive) files to any OCI-compliant registry

# ============================================================================
# Configuration
# ============================================================================

# Resolve paths relative to this script so it can run from any directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# wasmCloud CLI (`wash`) writes state under $HOME. In sandboxed environments this may be blocked,
# so default to a repo-local home (also useful for reproducible pushes).
WASH_HOME="${WASH_HOME:-${SCRIPT_DIR}/.wash-home}"
mkdir -p "${WASH_HOME}"

wash_cmd() {
    HOME="${WASH_HOME}" wash "$@"
}

# Registry configuration
REGISTRY="${PROVIDER_REGISTRY:-registry.kube-system.svc.cluster.local:80}"
PUSH_REGISTRY="${REGISTRY}"
REGISTRY_TYPE="${PROVIDER_REGISTRY_TYPE:-local}"  # local, gitlab, dockerhub, generic
TAG="${PROVIDER_TAG:-v1.0.0}"
CI_REGISTRY_IMAGE="${CI_REGISTRY_IMAGE:-}"  # GitLab CI variable

# Authentication (for remote registries)
REGISTRY_USERNAME="${REGISTRY_USERNAME:-}"
REGISTRY_PASSWORD="${REGISTRY_PASSWORD:-}"

# All Ekko custom providers
# Format: "provider-name:directory-name"
PROVIDERS=(
  "alert-scheduler:alert-scheduler"
  "ducklake-write:ducklake-write"
  "ducklake-read:ducklake-read"
  "websocket-notification:websocket-notification-provider"
  "email-notification:email-notification-provider"
  "slack-notification:slack-notification-provider"
  "telegram-notification:telegram-notification-provider"
  "webhook-notification:webhook-notification-provider"
  "newheads-evm:newheads-evm"
  "http-rpc:http-rpc"
  # Note: abi-decoder is an ACTOR (WASM component), not a provider - see push-actors-to-registry.sh
  "polars-eval:polars-eval"
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
    elif [[ "$REGISTRY" == *"docker.io"* ]]; then
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
        *)
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
    local provider_name=$1
    case "$REGISTRY_TYPE" in
        gitlab)
            if [ -n "$CI_REGISTRY_IMAGE" ]; then
                echo "${CI_REGISTRY_IMAGE}/wasmcloud/${provider_name}:${TAG}"
            else
                echo "${REGISTRY}/wasmcloud/${provider_name}:${TAG}"
            fi
            ;;
        dockerhub)
            echo "${PUSH_REGISTRY}/${provider_name}:${TAG}"
            ;;
        *)
            echo "${PUSH_REGISTRY}/${provider_name}:${TAG}"
            ;;
    esac
}

# ============================================================================
# Main Script
# ============================================================================

echo ""
echo "🚀 Ekko wasmCloud Provider Registry Push"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Configuration:"
echo "  Registry:      $REGISTRY"
if [ "$PUSH_REGISTRY" != "$REGISTRY" ]; then
    echo "  Push Registry: $PUSH_REGISTRY"
fi
echo "  Type:          $REGISTRY_TYPE"
echo "  Tag:           $TAG"
echo "  Providers:     ${#PROVIDERS[@]} providers"
echo ""

# Authenticate with registry
authenticate_registry

# Check registry connectivity
if ! check_registry_connectivity; then
    exit 1
fi

echo ""
log_info "Pushing providers to registry..."
echo ""

# Push each provider
SUCCESSFUL=0
FAILED=0

for provider_spec in "${PROVIDERS[@]}"; do
  IFS=':' read -r provider_name dir_name <<< "$provider_spec"
  par_file="${SCRIPT_DIR}/providers/${dir_name}/build/${provider_name}.par.gz"

  if [ ! -f "$par_file" ]; then
    log_error "PAR file not found: $par_file"
    log_info "Run './build.sh' or './build-provider.sh $dir_name' first to build providers"
    ((FAILED++))
    continue
  fi

  # Build full image reference
  registry_url=$(build_image_reference "$provider_name")

  echo "📦 Pushing: $provider_name"
  echo "   Source: $par_file"
  echo "   Target: $registry_url"

  # Use wash to push provider PAR file as OCI artifact
  # wasmCloud 1.0 uses PAR (Provider Archive) files for providers
  if wash_cmd push "$registry_url" "$par_file" $INSECURE_FLAG --allow-latest 2>/dev/null; then
    log_success "Success"
    ((SUCCESSFUL++))

    # Also push as latest tag
    registry_url_latest="${PUSH_REGISTRY}/${provider_name}:latest"
    wash_cmd push "$registry_url_latest" "$par_file" $INSECURE_FLAG 2>/dev/null || log_warning "Failed to push latest tag"
  else
    log_warning "Failed with wash - trying fallback method"
    # Fallback: use wash without --allow-latest
    if wash_cmd push "$registry_url" "$par_file" $INSECURE_FLAG 2>/dev/null; then
      log_success "Success (fallback)"
      ((SUCCESSFUL++))
    else
      log_error "Both methods failed for $provider_name"
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
log_success "$SUCCESSFUL providers pushed successfully"
if [ $FAILED -gt 0 ]; then
    log_error "$FAILED providers failed to push"
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

# Exit with error if any providers failed
if [ $FAILED -gt 0 ]; then
    exit 1
fi

log_success "All providers pushed successfully!"
echo ""
