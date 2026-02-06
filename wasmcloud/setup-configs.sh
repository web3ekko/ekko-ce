#!/bin/bash
set -e

# ============================================================================
# Setup wasmCloud Configs
# ============================================================================
# Pre-creates all configs in NATS KV store before WADM deployment.
# IMPORTANT: Configs stored in NATS KV are ephemeral and may be lost on restart.
# This script MUST be run before each deployment to ensure configs exist.
#
# Per PRD Issue 9: "Configs created with wash config put are stored in NATS KV
# store as ephemeral entries. These may be lost when WADM deployment restarts,
# wasmCloud host pods restart, or NATS server restarts."
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

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

log_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# ============================================================================
# Configuration (can be overridden via environment variables)
# ============================================================================

# Infrastructure URLs
NAMESPACE="${NAMESPACE:-${WASMCLOUD_LATTICE:-ekko-dev}}"
WASMCLOUD_LATTICE="${WASMCLOUD_LATTICE:-ekko-dev}"
CONFIG_BUCKET="${CONFIG_BUCKET:-CONFIGDATA_${WASMCLOUD_LATTICE}}"
REDIS_URL="${REDIS_URL:-redis://:redis123@redis-master.${NAMESPACE}.svc.cluster.local:6379}"
NATS_URL="${NATS_URL:-nats://nats-headless.${NAMESPACE}.svc.cluster.local:4222}"

# S3/MinIO configuration for DuckLake
S3_ENDPOINT="${S3_ENDPOINT:-http://host.docker.internal:9000}"
S3_BUCKET="${S3_BUCKET:-ekko-ducklake}"
S3_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID:-minioadmin}"
S3_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY:-minioadmin123}"
S3_REGION="${S3_REGION:-us-east-1}"

# PostgreSQL configuration for DuckLake metadata catalog
POSTGRES_HOST="${DUCKLAKE_POSTGRES_HOST:-${POSTGRES_HOST:-postgresql.${NAMESPACE}.svc.cluster.local}}"
POSTGRES_PORT="${DUCKLAKE_POSTGRES_PORT:-${POSTGRES_PORT:-5432}}"
POSTGRES_USER="${DUCKLAKE_POSTGRES_USER:-${POSTGRES_USER:-ekko}}"
POSTGRES_PASSWORD="${DUCKLAKE_POSTGRES_PASSWORD:-${POSTGRES_PASSWORD:-${DB_PASSWORD:-ekko123}}}"
POSTGRES_DATABASE="${DUCKLAKE_POSTGRES_DATABASE:-${POSTGRES_DATABASE:-${POSTGRES_DB:-ducklake_catalog}}}"

# DuckLake write subject (should be write-only; avoid subscribing to query/schema subjects)
DUCKLAKE_WRITE_SUBJECT="${DUCKLAKE_WRITE_SUBJECT:-ducklake.*.*.*.write}"
WADM_APP_NAME="${WADM_APP_NAME:-ekko-platform}"
WADM_CONFIG_PREFIX="${WADM_APP_NAME//-/_}"
USE_K8S_NATS="${USE_K8S_NATS:-auto}"
K8S_NATS_NAMESPACE="${K8S_NATS_NAMESPACE:-${NAMESPACE}}"
K8S_NATS_DEPLOYMENT="${K8S_NATS_DEPLOYMENT:-nats-box}"
RESEND_API_KEY="${RESEND_API_KEY:-}"
TELEGRAM_WEBHOOK_PORT="${TELEGRAM_WEBHOOK_PORT:-8081}"
NEWHEADS_ENABLED="${NEWHEADS_ENABLED:-false}"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

build_json_from_pairs() {
    python3 - "$@" <<'PY'
import json
import sys

data = {}
for arg in sys.argv[1:]:
    if "=" not in arg:
        continue
    key, value = arg.split("=", 1)
    data[key] = value

print(json.dumps(data, separators=(",", ":")))
PY
}

put_config_wash() {
    local config_name="$1"
    shift
    wash config put "$config_name" "$@"
}

put_config_k8s() {
    local config_name="$1"
    shift
    local config_json
    config_json="$(build_json_from_pairs "$@")"
    kubectl exec -n "${K8S_NATS_NAMESPACE}" "deploy/${K8S_NATS_DEPLOYMENT}" -- \
        nats --server "${NATS_URL}" kv put "${CONFIG_BUCKET}" "${config_name}" "${config_json}"
}

select_backend() {
    if [[ "${USE_K8S_NATS}" == "true" ]]; then
        echo "k8s"
        return 0
    fi

    if [[ "${USE_K8S_NATS}" == "false" ]]; then
        echo "wash"
        return 0
    fi

    if command_exists wash; then
        echo "wash"
        return 0
    fi

    if command_exists kubectl; then
        echo "k8s"
        return 0
    fi

    echo "none"
    return 0
}

CONFIG_BACKEND="$(select_backend)"
if [[ "${CONFIG_BACKEND}" == "wash" ]] && ! command_exists wash; then
    log_error "wash CLI not found and USE_K8S_NATS is disabled"
    exit 1
fi

if [[ "${CONFIG_BACKEND}" == "k8s" ]] && ! command_exists kubectl; then
    log_error "kubectl not found and USE_K8S_NATS is enabled"
    exit 1
fi

if [[ "${CONFIG_BACKEND}" == "k8s" ]] && ! command_exists python3; then
    log_error "python3 is required to build config payloads for k8s backend"
    exit 1
fi

put_config() {
    local base_name="$1"
    shift
    local prefixed_name="${WADM_CONFIG_PREFIX}-${base_name//-/_}"
    local status=0

    if [[ "${CONFIG_BACKEND}" == "k8s" ]]; then
        put_config_k8s "$base_name" "$@" || status=1
    else
        put_config_wash "$base_name" "$@" || status=1
    fi
    if [[ "$prefixed_name" != "$base_name" ]]; then
        if [[ "${CONFIG_BACKEND}" == "k8s" ]]; then
            put_config_k8s "$prefixed_name" "$@" || status=1
        else
            put_config_wash "$prefixed_name" "$@" || status=1
        fi
    fi

    return $status
}

echo -e "${CYAN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   wasmCloud Config Setup                                  ║
║   Pre-creating configs in NATS KV store                   ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

log_section "Configuration"
echo "Namespace:       ${NAMESPACE}"
echo "Lattice:         ${WASMCLOUD_LATTICE}"
echo "Config backend:  ${CONFIG_BACKEND}"
echo "Config bucket:   ${CONFIG_BUCKET}"
echo "Redis URL:       ${REDIS_URL}"
echo "NATS URL:        ${NATS_URL}"
echo "S3 Endpoint:     ${S3_ENDPOINT}"
echo "S3 Bucket:       ${S3_BUCKET}"
echo "PostgreSQL Host: ${POSTGRES_HOST}:${POSTGRES_PORT}"
echo "Telegram Port:   ${TELEGRAM_WEBHOOK_PORT}"
echo ""

if [[ -z "${RESEND_API_KEY}" ]]; then
    log_warning "RESEND_API_KEY is not set; email-notification provider will fail to start"
fi

# ============================================================================
# Create Handler Configs (NATS Messaging Subscriptions)
# ============================================================================

log_section "Creating Handler Configs (NATS Subscriptions)"

# NOTE: These handler configs are consumed by the `messaging-nats` provider.
# Always include `CLUSTER_URIS` so handlers publish/subscribe on the intended NATS
# bus (important when the host uses a leaf NATS).

# Health check handler
log_info "Creating health-check-handler config..."
put_config health-check-handler subscriptions="system.health" CLUSTER_URIS="${NATS_URL}" && \
    log_success "health-check-handler" || log_error "health-check-handler failed"

# ETH raw transactions handler
# blockchain.ethereum.>.transactions.raw catches all subnets (mainnet, sepolia, etc.)
log_info "Creating eth-raw-handler config..."
put_config eth-raw-handler subscriptions="newheads.ethereum.mainnet.evm, blockchain.ethereum.>.transactions.raw" CLUSTER_URIS="${NATS_URL}" && \
    log_success "eth-raw-handler" || log_error "eth-raw-handler failed"

# Alerts-processor handler
log_info "Creating alerts-processor-handler config..."
put_config alerts-processor-handler subscriptions="alerts.jobs.create.>" CLUSTER_URIS="${NATS_URL}" && \
    log_success "alerts-processor-handler" || log_error "alerts-processor-handler failed"

# BTC raw transactions handler
# blockchain.bitcoin.>.transactions.raw catches all subnets (mainnet, testnet)
log_info "Creating btc-raw-handler config..."
put_config btc-raw-handler subscriptions="newheads.*.*.btc, blockchain.bitcoin.>.transactions.raw" CLUSTER_URIS="${NATS_URL}" && \
    log_success "btc-raw-handler" || log_error "btc-raw-handler failed"

# SOL raw transactions handler
# blockchain.solana.>.transactions.raw catches all subnets (mainnet, devnet, testnet)
log_info "Creating sol-raw-handler config..."
put_config sol-raw-handler subscriptions="newheads.*.*.svm, blockchain.solana.>.transactions.raw" CLUSTER_URIS="${NATS_URL}" && \
    log_success "sol-raw-handler" || log_error "sol-raw-handler failed"

# ETH process transactions handler
# eth-raw-transactions publishes normalized raw txs to `transactions.raw.evm`
log_info "Creating eth-process-handler config..."
put_config eth-process-handler subscriptions="transactions.raw.evm" CLUSTER_URIS="${NATS_URL}" && \
    log_success "eth-process-handler" || log_error "eth-process-handler failed"

# ETH transfers handler
# eth-process-transactions publishes transfer-only txs to `transfer-transactions.*.*.evm.raw`
log_info "Creating eth-transfers-handler config..."
put_config eth-transfers-handler subscriptions="transfer-transactions.*.*.evm.raw" CLUSTER_URIS="${NATS_URL}" && \
    log_success "eth-transfers-handler" || log_error "eth-transfers-handler failed"

# ETH contract creation handler
# blockchain.ethereum.>.contracts.creation catches all subnets
log_info "Creating eth-contract-creation-handler config..."
put_config eth-contract-creation-handler subscriptions="blockchain.ethereum.>.contracts.creation" CLUSTER_URIS="${NATS_URL}" && \
    log_success "eth-contract-creation-handler" || log_error "eth-contract-creation-handler failed"

# ETH contract transaction handler
# blockchain.ethereum.>.contracts.transactions and blockchain.ethereum.>.contracts.decoded
log_info "Creating eth-contract-transaction-handler config..."
put_config eth-contract-transaction-handler subscriptions="blockchain.ethereum.>.contracts.transactions, blockchain.ethereum.>.contracts.decoded" CLUSTER_URIS="${NATS_URL}" && \
    log_success "eth-contract-transaction-handler" || log_error "eth-contract-transaction-handler failed"

# Transaction processor handler
# blockchain.>.>.transactions.> catches all networks and all subnets
log_info "Creating transaction-processor-handler config..."
put_config transaction-processor-handler subscriptions="blockchain.>.>.transactions.>" CLUSTER_URIS="${NATS_URL}" && \
    log_success "transaction-processor-handler" || log_error "transaction-processor-handler failed"

# Notification router handler
log_info "Creating notification-router-handler config..."
put_config notification-router-handler subscriptions="alerts.triggered.>, notifications.send.immediate.>" CLUSTER_URIS="${NATS_URL}" && \
    log_success "notification-router-handler" || log_error "notification-router-handler failed"

# ABI decoder handler
# blockchain.>.>.contracts.transactions catches all networks/subnets
# blockchain.abi.decode.> catches decode requests for all networks/subnets
log_info "Creating abi-decoder-handler config..."
put_config abi-decoder-handler subscriptions="blockchain.>.>.contracts.transactions, blockchain.abi.decode.>" CLUSTER_URIS="${NATS_URL}" && \
    log_success "abi-decoder-handler" || log_error "abi-decoder-handler failed"

# Transaction DuckLake writer handler
log_info "Creating transaction-ducklake-writer-handler config..."
put_config transaction-ducklake-writer-handler subscriptions="blockchain.>.>.transactions.processed, blockchain.>.>.contracts.decoded" CLUSTER_URIS="${NATS_URL}" && \
    log_success "transaction-ducklake-writer-handler" || log_error "transaction-ducklake-writer-handler failed"

# ============================================================================
# Create NATS Consumer Configs (Actor outbound messaging)
# ============================================================================

log_section "Creating NATS Consumer Configs (Outbound Messaging)"

NATS_CONSUMER_CONFIGS=(
    "nats-consumer-health-check"
    "nats-consumer-eth-raw-transactions"
    "nats-consumer-evm-logs-ingestion"
    "nats-consumer-alerts-processor"
    "nats-consumer-btc-raw-transactions"
    "nats-consumer-sol-raw-transactions"
    "nats-consumer-eth-process-transactions"
    "nats-consumer-eth-transfers-processor"
    "nats-consumer-eth-contract-creation-processor"
    "nats-consumer-eth-contract-transaction-processor"
    "nats-consumer-transaction-processor"
    "nats-consumer-notification-router"
    "nats-consumer-abi-decoder"
    "nats-consumer-transaction-ducklake-writer"
)

for config_name in "${NATS_CONSUMER_CONFIGS[@]}"; do
    log_info "Creating ${config_name} config..."
    put_config "${config_name}" CLUSTER_URIS="${NATS_URL}" && \
        log_success "${config_name}" || log_error "${config_name} failed"
done

# ============================================================================
# Create Redis Configs (Actor KeyValue Store)
# ============================================================================

log_section "Creating Redis Configs (KeyValue Store)"

REDIS_ACTORS=(
    "eth-raw-transactions-redis"
    "alerts-processor-redis"
    "btc-raw-transactions-redis"
    "sol-raw-transactions-redis"
    "eth-process-transactions-redis"
    "eth-transfers-processor-redis"
    "eth-contract-creation-processor-redis"
    "eth-contract-transaction-processor-redis"
    "transaction-processor-redis"
    "notification-router-redis"
    "abi-decoder-redis"
)

for config_name in "${REDIS_ACTORS[@]}"; do
    log_info "Creating ${config_name} config..."
    put_config "${config_name}" url="${REDIS_URL}" && \
        log_success "${config_name}" || log_error "${config_name} failed"
done

# ============================================================================
# Create Provider Configs
# ============================================================================

log_section "Creating Provider Configs"

# Core capabilities used by most actors/providers.
log_info "Creating redis-keyvalue-config..."
put_config redis-keyvalue-config url="${REDIS_URL}" && \
    log_success "redis-keyvalue-config" || log_error "redis-keyvalue-config failed"

log_info "Creating nats-messaging-config..."
put_config nats-messaging-config CLUSTER_URIS="${NATS_URL}" && \
    log_success "nats-messaging-config" || log_error "nats-messaging-config failed"

# Newheads EVM Provider
log_info "Creating newheads-evm-config..."
put_config newheads-evm-config \
    redis_url="${REDIS_URL}" \
    nats_url="${NATS_URL}" \
    enabled="${NEWHEADS_ENABLED}" && \
    log_success "newheads-evm-config" || log_error "newheads-evm-config failed"

# Alert Scheduler Provider
log_info "Creating alert-scheduler-config..."
put_config alert-scheduler-config \
    redis_url="${REDIS_URL}" \
    nats_url="${NATS_URL}" && \
    log_success "alert-scheduler-config" || log_error "alert-scheduler-config failed"

# HTTP RPC Provider
log_info "Creating http-rpc-config..."
put_config http-rpc-config \
    redis_url="${REDIS_URL}" && \
    log_success "http-rpc-config" || log_error "http-rpc-config failed"

# Email Notification Provider
log_info "Creating email-notification-config..."
put_config email-notification-config \
    redis_url="${REDIS_URL}" \
    nats_url="${NATS_URL}" \
    resend_api_key="${RESEND_API_KEY}" && \
    log_success "email-notification-config" || log_error "email-notification-config failed"

# WebSocket Notification Provider
log_info "Creating websocket-notification-config..."
put_config websocket-notification-config \
    redis_url="${REDIS_URL}" \
    nats_url="${NATS_URL}" && \
    log_success "websocket-notification-config" || log_error "websocket-notification-config failed"

# Slack Notification Provider
log_info "Creating slack-notification-config..."
put_config slack-notification-config \
    redis_url="${REDIS_URL}" \
    nats_url="${NATS_URL}" && \
    log_success "slack-notification-config" || log_error "slack-notification-config failed"

# Telegram Notification Provider
log_info "Creating telegram-notification-config..."
put_config telegram-notification-config \
    redis_url="${REDIS_URL}" \
    nats_url="${NATS_URL}" \
    webhook_port="${TELEGRAM_WEBHOOK_PORT}" && \
    log_success "telegram-notification-config" || log_error "telegram-notification-config failed"

# Webhook Notification Provider
log_info "Creating webhook-notification-config..."
put_config webhook-notification-config \
    redis_url="${REDIS_URL}" \
    nats_url="${NATS_URL}" && \
    log_success "webhook-notification-config" || log_error "webhook-notification-config failed"

# Polars Eval Provider
log_info "Creating polars-eval-config..."
put_config polars-eval-config \
    redis_url="${REDIS_URL}" \
    nats_url="${NATS_URL}" && \
    log_success "polars-eval-config" || log_error "polars-eval-config failed"

# DuckLake Write Provider (most complex config)
# Create with both standard name AND WADM-prefixed name for compatibility
# WADM prefixes config names with app_name when passing to providers
log_info "Creating ducklake-write-config..."
put_config ducklake-write-config \
    nats_url="${NATS_URL}" \
    redis_url="${REDIS_URL}" \
    ducklake_s3_endpoint="${S3_ENDPOINT}" \
    ducklake_s3_bucket="${S3_BUCKET}" \
    ducklake_s3_access_key_id="${S3_ACCESS_KEY_ID}" \
    ducklake_s3_secret_access_key="${S3_SECRET_ACCESS_KEY}" \
    ducklake_s3_region="${S3_REGION}" \
    ducklake_postgres_host="${POSTGRES_HOST}" \
    ducklake_postgres_port="${POSTGRES_PORT}" \
    ducklake_postgres_user="${POSTGRES_USER}" \
    ducklake_postgres_password="${POSTGRES_PASSWORD}" \
    ducklake_postgres_database="${POSTGRES_DATABASE}" \
    ducklake_write_subject="${DUCKLAKE_WRITE_SUBJECT}" \
    ducklake_warehouse_path="ekko/ducklake" && \
    log_success "ducklake-write-config" || log_error "ducklake-write-config failed"

# DuckLake Read Provider (query + schema discovery)
log_info "Creating ducklake-read-config..."
put_config ducklake-read-config \
    nats_url="${NATS_URL}" \
    redis_url="${REDIS_URL}" \
    ducklake_s3_endpoint="${S3_ENDPOINT}" \
    ducklake_s3_bucket="${S3_BUCKET}" \
    ducklake_s3_access_key_id="${S3_ACCESS_KEY_ID}" \
    ducklake_s3_secret_access_key="${S3_SECRET_ACCESS_KEY}" \
    ducklake_s3_region="${S3_REGION}" \
    ducklake_postgres_host="${POSTGRES_HOST}" \
    ducklake_postgres_port="${POSTGRES_PORT}" \
    ducklake_postgres_user="${POSTGRES_USER}" \
    ducklake_postgres_password="${POSTGRES_PASSWORD}" \
    ducklake_postgres_database="${POSTGRES_DATABASE}" \
    ducklake_query_subject="ducklake.*.*.*.query" \
    ducklake_schema_list_subject="ducklake.schema.list" \
    ducklake_schema_get_subject="ducklake.schema.get" \
    ducklake_warehouse_path="ekko/ducklake" && \
    log_success "ducklake-read-config" || log_error "ducklake-read-config failed"

# ============================================================================
# Verify Configs
# ============================================================================

log_section "Verifying Configs"

log_info "Verifying config access..."
if [[ "${CONFIG_BACKEND}" == "k8s" ]]; then
    kubectl exec -n "${K8S_NATS_NAMESPACE}" "deploy/${K8S_NATS_DEPLOYMENT}" -- \
        nats --server "${NATS_URL}" kv ls "${CONFIG_BUCKET}" 2>&1 || \
        log_warning "Could not list configs with nats kv ls"
elif wash config --help 2>/dev/null | grep -q "list"; then
    wash config list 2>&1 || log_warning "Could not list configs"
else
    log_warning "wash config list not supported; use wash config get <name> to inspect configs"
fi

log_section "Config Setup Complete"
log_success "All wasmCloud configs have been created in NATS KV store"
echo ""
echo "NOTE: These configs are ephemeral and will be lost on restart."
echo "Run this script again after any NATS/WADM/wasmCloud restart."
echo ""
