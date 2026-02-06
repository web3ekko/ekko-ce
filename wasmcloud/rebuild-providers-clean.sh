#!/bin/bash
# =============================================================================
# DEPRECATED: This script's functionality has been merged into build.sh
# =============================================================================
#
# Use build.sh instead:
#
#   # Build all actors and providers for Linux (default)
#   ./build.sh
#
#   # Build providers only (skip actors)
#   SKIP_ACTOR_BUILD=true ./build.sh
#
#   # Build and push to registry
#   PUSH_TO_REGISTRY=true ./build.sh
#
# The build.sh script now handles:
#   - Environment file loading (.env.orbstack by default)
#   - Linux cross-compilation for all providers
#   - PAR file creation with correct --arch aarch64-linux
#   - Automatic provider categorization (musl vs glibc)
#
# This script is kept for reference only and will be removed in a future update.
# =============================================================================

echo "⚠️  DEPRECATED: This script has been superseded by build.sh"
echo "   Please use: ./build.sh"
echo ""
echo "   Options:"
echo "     SKIP_ACTOR_BUILD=true ./build.sh   # Build providers only"
echo "     PUSH_TO_REGISTRY=true ./build.sh   # Build and push to registry"
echo ""
read -p "Continue anyway? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Exiting. Use ./build.sh instead."
    exit 0
fi

# Original script continues below (deprecated)
set -e

PROJECT_ROOT=$(cd ../.. && pwd)
WASMCLOUD_DIR="$PROJECT_ROOT/apps/wasmcloud"

echo "🔨 Rebuilding alert-scheduler-provider..."
docker run --rm --platform linux/arm64 \
  -v "$PROJECT_ROOT:/project" \
  -w /project/apps/wasmcloud \
  rust:alpine sh -c '
    apk add --no-cache musl-dev openssl-dev openssl-libs-static pkgconfig g++ &&
    rustup target add aarch64-unknown-linux-musl &&
    touch providers/alert-scheduler/src/bin/alert-scheduler-provider.rs &&
    OPENSSL_STATIC=1 OPENSSL_LIB_DIR=/usr/lib OPENSSL_INCLUDE_DIR=/usr/include \
    cargo build --release --target aarch64-unknown-linux-musl \
      -p alert-scheduler-provider --bin alert-scheduler-provider &&
    cp target/aarch64-unknown-linux-musl/release/alert-scheduler-provider \
      providers/alert-scheduler/build/alert-scheduler-provider-aarch64-linux
  '

echo "🔨 Rebuilding http-rpc-provider..."
docker run --rm --platform linux/arm64 \
  -v "$PROJECT_ROOT:/project" \
  -w /project/apps/wasmcloud \
  rust:alpine sh -c '
    apk add --no-cache musl-dev openssl-dev openssl-libs-static pkgconfig g++ &&
    rustup target add aarch64-unknown-linux-musl &&
    touch providers/http-rpc/src/bin/http-rpc-provider.rs &&
    OPENSSL_STATIC=1 OPENSSL_LIB_DIR=/usr/lib OPENSSL_INCLUDE_DIR=/usr/include \
    cargo build --release --target aarch64-unknown-linux-musl \
      -p http-rpc-provider --bin http-rpc-provider &&
    cp target/aarch64-unknown-linux-musl/release/http-rpc-provider \
      providers/http-rpc/build/http-rpc-provider-aarch64-linux
  '

echo "🔨 Rebuilding slack-notification-provider..."
mkdir -p providers/slack-notification-provider/build
docker run --rm --platform linux/arm64 \
  -v "$PROJECT_ROOT:/project" \
  -w /project/apps/wasmcloud \
  rust:alpine sh -c '
    apk add --no-cache musl-dev openssl-dev openssl-libs-static pkgconfig g++ &&
    rustup target add aarch64-unknown-linux-musl &&
    touch providers/slack-notification-provider/src/bin/slack-notification-provider.rs &&
    OPENSSL_STATIC=1 OPENSSL_LIB_DIR=/usr/lib OPENSSL_INCLUDE_DIR=/usr/include \
    cargo build --release --target aarch64-unknown-linux-musl \
      -p slack-notification-provider --bin slack-notification-provider &&
    cp target/aarch64-unknown-linux-musl/release/slack-notification-provider \
      providers/slack-notification-provider/build/slack-notification-provider-aarch64-linux
  '

echo "🔨 Rebuilding telegram-notification-provider..."
mkdir -p providers/telegram-notification-provider/build
docker run --rm --platform linux/arm64 \
  -v "$PROJECT_ROOT:/project" \
  -w /project/apps/wasmcloud \
  rust:alpine sh -c '
    apk add --no-cache musl-dev openssl-dev openssl-libs-static pkgconfig g++ &&
    rustup target add aarch64-unknown-linux-musl &&
    touch providers/telegram-notification-provider/src/main.rs &&
    OPENSSL_STATIC=1 OPENSSL_LIB_DIR=/usr/lib OPENSSL_INCLUDE_DIR=/usr/include \
    cargo build --release --target aarch64-unknown-linux-musl \
      -p telegram-notification-provider --bin telegram-notification-provider &&
    cp target/aarch64-unknown-linux-musl/release/telegram-notification-provider \
      providers/telegram-notification-provider/build/telegram-notification-provider-aarch64-linux
  '

echo "🔨 Rebuilding webhook-notification-provider..."
mkdir -p providers/webhook-notification-provider/build
docker run --rm --platform linux/arm64 \
  -v "$PROJECT_ROOT:/project" \
  -w /project/apps/wasmcloud \
  rust:alpine sh -c '
    apk add --no-cache musl-dev openssl-dev openssl-libs-static pkgconfig g++ &&
    rustup target add aarch64-unknown-linux-musl &&
    touch providers/webhook-notification-provider/src/main.rs &&
    OPENSSL_STATIC=1 OPENSSL_LIB_DIR=/usr/lib OPENSSL_INCLUDE_DIR=/usr/include \
    cargo build --release --target aarch64-unknown-linux-musl \
      -p webhook-notification-provider --bin webhook-notification-provider &&
    cp target/aarch64-unknown-linux-musl/release/webhook-notification-provider \
      providers/webhook-notification-provider/build/webhook-notification-provider-aarch64-linux
  '

# =============================================================================
# GLIBC PROVIDERS (for DuckDB extensions compatibility)
# =============================================================================
# DuckDB extensions are only available for glibc platforms, NOT musl.
# See PRD Issue 17: DuckDB Extensions Unavailable for linux_arm64_musl

echo "🔨 Rebuilding ducklake-write-provider (glibc for DuckDB extensions)..."
mkdir -p providers/ducklake-write/build
docker run --rm --platform linux/arm64 \
  -v "$PROJECT_ROOT:/project" \
  -w /project/apps/wasmcloud \
  rust:slim sh -c '
    apt-get update && apt-get install -y pkg-config libssl-dev g++ &&
    rustup target add aarch64-unknown-linux-gnu &&
    touch providers/ducklake-write/src/bin/ducklake-write-provider.rs &&
    cargo build --release --target aarch64-unknown-linux-gnu \
      -p ducklake-write-provider --bin ducklake-write-provider &&
    cp target/aarch64-unknown-linux-gnu/release/ducklake-write-provider \
      providers/ducklake-write/build/ducklake-write-provider-aarch64-linux
  '

echo "🔨 Rebuilding ducklake-read-provider (glibc for DuckDB extensions)..."
mkdir -p providers/ducklake-read/build
docker run --rm --platform linux/arm64 \
  -v "$PROJECT_ROOT:/project" \
  -w /project/apps/wasmcloud \
  rust:slim sh -c '
    apt-get update && apt-get install -y pkg-config libssl-dev g++ &&
    rustup target add aarch64-unknown-linux-gnu &&
    touch providers/ducklake-read/src/bin/ducklake-read-provider.rs &&
    cargo build --release --target aarch64-unknown-linux-gnu \
      -p ducklake-read-provider --bin ducklake-read-provider &&
    cp target/aarch64-unknown-linux-gnu/release/ducklake-read-provider \
      providers/ducklake-read/build/ducklake-read-provider-aarch64-linux
  '

echo "✅ Builds complete!"
