#!/bin/bash

# WADM Deployment Verification Script
# Verifies that all actors and providers defined in the WADM manifest
# are successfully deployed and healthy. Uses the manifest as source of truth.

set -e

# Configuration
NAMESPACE="${NAMESPACE:-ekko}"
LATTICE="${LATTICE:-ekko-prod}"
MANIFEST_FILE="${MANIFEST_FILE:-manifests/ekko-actors-generated.yaml}"
APPLICATION_NAME="${APPLICATION_NAME:-ekko-platform}"
EXPECTED_VERSION="${EXPECTED_VERSION:-v1.0.0}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "🔍 WADM Deployment Verification"
echo "========================================"
echo "Namespace:    ${NAMESPACE}"
echo "Lattice:      ${LATTICE}"
echo "Application:  ${APPLICATION_NAME}"
echo "Manifest:     ${MANIFEST_FILE}"
echo "Expected Ver: ${EXPECTED_VERSION}"
echo ""

# Check prerequisites
echo "📋 Checking Prerequisites..."

if ! command -v wash &> /dev/null; then
    echo -e "${RED}❌ wash CLI is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ wash CLI installed${NC}"

if ! command -v yq &> /dev/null; then
    echo -e "${RED}❌ yq is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ yq installed${NC}"

if ! command -v jq &> /dev/null; then
    echo -e "${RED}❌ jq is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ jq installed${NC}"

if [ ! -f "$MANIFEST_FILE" ]; then
    echo -e "${RED}❌ Manifest file not found: ${MANIFEST_FILE}${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Manifest file found${NC}"
echo ""

# Parse manifest to extract expected components
echo "📝 Parsing Manifest for Expected Components..."

# Extract actor names
EXPECTED_ACTORS=$(yq eval '.spec.components[] | select(.type == "actor") | .name' "$MANIFEST_FILE")
EXPECTED_ACTOR_COUNT=$(echo "$EXPECTED_ACTORS" | grep -v '^$' | wc -l | tr -d ' ')

# Extract provider names
EXPECTED_PROVIDERS=$(yq eval '.spec.components[] | select(.type == "capability") | .name' "$MANIFEST_FILE")
EXPECTED_PROVIDER_COUNT=$(echo "$EXPECTED_PROVIDERS" | grep -v '^$' | wc -l | tr -d ' ')

echo -e "${BLUE}Expected Components:${NC}"
echo "  Actors:    ${EXPECTED_ACTOR_COUNT}"
echo "  Providers: ${EXPECTED_PROVIDER_COUNT}"
echo ""

# Get deployment status from WADM
echo "🔍 Querying WADM Deployment Status..."

# Set environment for wash
export WASMCLOUD_LATTICE=${LATTICE}

# Get application status
if ! DEPLOYMENT_STATUS=$(wash app status "${APPLICATION_NAME}" --output json 2>&1); then
    echo -e "${RED}❌ Failed to get application status${NC}"
    echo "$DEPLOYMENT_STATUS"
    exit 1
fi

# Check if application exists
if echo "$DEPLOYMENT_STATUS" | grep -q "not found"; then
    echo -e "${RED}❌ Application '${APPLICATION_NAME}' not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Application status retrieved${NC}"
echo ""

# Verify deployed version
echo "🏷️  Verifying Deployment Version..."
DEPLOYED_VERSION=$(echo "$DEPLOYMENT_STATUS" | jq -r '.version // "unknown"')

if [ "$DEPLOYED_VERSION" = "$EXPECTED_VERSION" ]; then
    echo -e "${GREEN}✅ Version matches: ${DEPLOYED_VERSION}${NC}"
else
    echo -e "${YELLOW}⚠️  Version mismatch: expected ${EXPECTED_VERSION}, got ${DEPLOYED_VERSION}${NC}"
    echo "   (This may be expected if version wasn't updated)"
fi
echo ""

# Verify application status
echo "🎯 Verifying Application Status..."
APP_STATUS=$(echo "$DEPLOYMENT_STATUS" | jq -r '.status // "unknown"')

if [ "$APP_STATUS" = "Deployed" ] || [ "$APP_STATUS" = "Reconciling" ]; then
    echo -e "${GREEN}✅ Application status: ${APP_STATUS}${NC}"
else
    echo -e "${RED}❌ Application status: ${APP_STATUS} (UNHEALTHY)${NC}"
    exit 1
fi
echo ""

# Verify each actor
echo "🎭 Verifying Actors..."
ACTOR_FAILURES=0

while IFS= read -r actor; do
    # Skip empty lines
    [ -z "$actor" ] && continue

    # Check if actor exists in deployment
    ACTOR_INFO=$(echo "$DEPLOYMENT_STATUS" | jq -r ".components[] | select(.name == \"${actor}\")" 2>/dev/null)

    if [ -z "$ACTOR_INFO" ]; then
        echo -e "${RED}  ❌ ${actor}: NOT FOUND in deployment${NC}"
        ACTOR_FAILURES=$((ACTOR_FAILURES + 1))
        continue
    fi

    # Get actor status
    ACTOR_STATUS=$(echo "$ACTOR_INFO" | jq -r '.status // "unknown"')

    if [ "$ACTOR_STATUS" = "Deployed" ] || [ "$ACTOR_STATUS" = "Running" ]; then
        echo -e "${GREEN}  ✅ ${actor}: ${ACTOR_STATUS}${NC}"
    else
        echo -e "${RED}  ❌ ${actor}: ${ACTOR_STATUS} (UNHEALTHY)${NC}"
        ACTOR_FAILURES=$((ACTOR_FAILURES + 1))
    fi
done <<< "$EXPECTED_ACTORS"

if [ $ACTOR_FAILURES -gt 0 ]; then
    echo -e "${RED}❌ ${ACTOR_FAILURES} actor(s) failed verification${NC}"
else
    echo -e "${GREEN}✅ All ${EXPECTED_ACTOR_COUNT} actors verified${NC}"
fi
echo ""

# Verify each provider
echo "🔌 Verifying Providers..."
PROVIDER_FAILURES=0

while IFS= read -r provider; do
    # Skip empty lines
    [ -z "$provider" ] && continue

    # Check if provider exists in deployment
    PROVIDER_INFO=$(echo "$DEPLOYMENT_STATUS" | jq -r ".components[] | select(.name == \"${provider}\")" 2>/dev/null)

    if [ -z "$PROVIDER_INFO" ]; then
        echo -e "${RED}  ❌ ${provider}: NOT FOUND in deployment${NC}"
        PROVIDER_FAILURES=$((PROVIDER_FAILURES + 1))
        continue
    fi

    # Get provider status
    PROVIDER_STATUS=$(echo "$PROVIDER_INFO" | jq -r '.status // "unknown"')

    if [ "$PROVIDER_STATUS" = "Deployed" ] || [ "$PROVIDER_STATUS" = "Running" ]; then
        echo -e "${GREEN}  ✅ ${provider}: ${PROVIDER_STATUS}${NC}"
    else
        echo -e "${RED}  ❌ ${provider}: ${PROVIDER_STATUS} (UNHEALTHY)${NC}"
        PROVIDER_FAILURES=$((PROVIDER_FAILURES + 1))
    fi
done <<< "$EXPECTED_PROVIDERS"

if [ $PROVIDER_FAILURES -gt 0 ]; then
    echo -e "${RED}❌ ${PROVIDER_FAILURES} provider(s) failed verification${NC}"
else
    echo -e "${GREEN}✅ All ${EXPECTED_PROVIDER_COUNT} providers verified${NC}"
fi
echo ""

# Summary
echo "========================================"
echo "📊 Verification Summary"
echo "========================================"
echo "Application:  ${APPLICATION_NAME}"
echo "Status:       ${APP_STATUS}"
echo "Version:      ${DEPLOYED_VERSION}"
echo ""
echo "Components:"
echo "  Actors:     ${EXPECTED_ACTOR_COUNT} expected, $((EXPECTED_ACTOR_COUNT - ACTOR_FAILURES)) verified"
echo "  Providers:  ${EXPECTED_PROVIDER_COUNT} expected, $((EXPECTED_PROVIDER_COUNT - PROVIDER_FAILURES)) verified"
echo ""

# Exit with failure if any component failed
TOTAL_FAILURES=$((ACTOR_FAILURES + PROVIDER_FAILURES))
if [ $TOTAL_FAILURES -gt 0 ]; then
    echo -e "${RED}❌ VERIFICATION FAILED: ${TOTAL_FAILURES} component(s) unhealthy${NC}"
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ VERIFICATION PASSED: All components healthy${NC}"
    echo ""
    exit 0
fi
