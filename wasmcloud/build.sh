#!/bin/bash
set -euo pipefail

# Build script for WasmCloud actors and providers
# Builds providers for Linux (aarch64-linux) by default for K8s deployment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$SCRIPT_DIR"

# =============================================================================
# Environment Configuration
# =============================================================================

# Load environment file (default: .env.orbstack)
ENV_FILE="${ENV_FILE:-.env.orbstack}"
if [[ "$ENV_FILE" = /* ]]; then
    if [ -f "$ENV_FILE" ]; then
        echo "📂 Loading environment from $ENV_FILE"
        set -a  # Auto-export variables
        source "$ENV_FILE"
        set +a
    else
        echo "⚠️  Environment file not found: $ENV_FILE"
    fi
elif [ -f "$PROJECT_ROOT/$ENV_FILE" ]; then
    echo "📂 Loading environment from $ENV_FILE"
    set -a  # Auto-export variables
    source "$PROJECT_ROOT/$ENV_FILE"
    set +a
elif [ -f "$PROJECT_ROOT/.env.orbstack" ]; then
    echo "📂 Loading environment from .env.orbstack"
    set -a
    source "$PROJECT_ROOT/.env.orbstack"
    set +a
else
    echo "⚠️  No environment file found, using defaults"
fi

# Configuration (from env file or defaults)
REGISTRY="${PROVIDER_REGISTRY:-${ACTOR_REGISTRY:-host.docker.internal:5001}}"
PROVIDER_VERSION="${PROVIDER_TAG:-v1.0.0}"
CREATE_PAR="${CREATE_PAR:-true}"
PUSH_TO_REGISTRY="${PUSH_TO_REGISTRY:-false}"

# Build options
SKIP_ACTOR_BUILD="${SKIP_ACTOR_BUILD:-false}"
SKIP_PROVIDER_BUILD="${SKIP_PROVIDER_BUILD:-false}"
BUILD_NATIVE="${BUILD_NATIVE:-false}"  # Set to true for local macOS testing only

# Target architecture for provider binaries (Linux)
# Supported: aarch64 (arm64) or x86_64 (amd64)
PROVIDER_ARCH="${PROVIDER_ARCH:-aarch64}"
case "${PROVIDER_ARCH}" in
  aarch64|arm64)
    LINUX_ARCH="aarch64"
    DOCKER_PLATFORM="linux/arm64"
    ;;
  x86_64|amd64)
    LINUX_ARCH="x86_64"
    DOCKER_PLATFORM="linux/amd64"
    ;;
  *)
    echo "❌ Unsupported PROVIDER_ARCH: ${PROVIDER_ARCH} (use aarch64 or x86_64)"
    exit 1
    ;;
esac
LINUX_MUSL_TARGET="${LINUX_ARCH}-unknown-linux-musl"
LINUX_GLIBC_TARGET="${LINUX_ARCH}-unknown-linux-gnu"
LINUX_ARCH_LABEL="${LINUX_ARCH}-linux"

# Rust cache directories (used by containerized provider builds)
CARGO_CACHE_DIR="${CARGO_CACHE_DIR:-${PROJECT_ROOT}/.cargo-home}"
RUSTUP_CACHE_DIR="${RUSTUP_CACHE_DIR:-${PROJECT_ROOT}/.rustup-home}"
mkdir -p "${CARGO_CACHE_DIR}" "${RUSTUP_CACHE_DIR}"
CONTAINER_CARGO_HOME="${CONTAINER_CARGO_HOME:-/usr/local/cargo}"
CONTAINER_RUSTUP_HOME="${CONTAINER_RUSTUP_HOME:-/usr/local/rustup}"

# Build backend (docker or zigbuild)
USE_ZIGBUILD="${USE_ZIGBUILD:-false}"

# Provider binary stripping (reduces PAR size)
STRIP_BINARIES="${STRIP_BINARIES:-true}"
PROVIDER_RUSTFLAGS="${PROVIDER_RUSTFLAGS:-${RUSTFLAGS:-}}"
if [ "${STRIP_BINARIES}" = "true" ]; then
    if [ -n "${PROVIDER_RUSTFLAGS}" ]; then
        PROVIDER_RUSTFLAGS="-C strip=symbols ${PROVIDER_RUSTFLAGS}"
    else
        PROVIDER_RUSTFLAGS="-C strip=symbols"
    fi
fi
DOCKER_RUSTFLAGS_ENV=()
if [ -n "${PROVIDER_RUSTFLAGS}" ]; then
    DOCKER_RUSTFLAGS_ENV=(-e "RUSTFLAGS=${PROVIDER_RUSTFLAGS}")
fi

# wasmCloud CLI (`wash`) writes state under $HOME. In sandboxed environments this may be blocked,
# so default to a repo-local home (also useful for reproducible builds).
WASH_HOME="${WASH_HOME:-${SCRIPT_DIR}/.wash-home}"
mkdir -p "${WASH_HOME}"

wash_cmd() {
    HOME="${WASH_HOME}" wash "$@"
}

echo ""
echo "🔧 Build Configuration:"
echo "  Registry: $REGISTRY"
echo "  Provider Version: $PROVIDER_VERSION"
echo "  PAR Creation: $CREATE_PAR"
echo "  Push to Registry: $PUSH_TO_REGISTRY"
echo "  Build Native: $BUILD_NATIVE"
echo "  Provider Arch: ${LINUX_ARCH_LABEL}"
echo "  Build Backend: $([ \"${USE_ZIGBUILD}\" = \"true\" ] && echo zigbuild || echo docker)"
echo "  Rust Cache (container): ${CONTAINER_CARGO_HOME}"
echo "  Strip Provider Binaries: $STRIP_BINARIES"
echo ""

# =============================================================================
# Actor Building (WASM - platform independent)
# =============================================================================

build_actor() {
    local actor=$1
    echo "  📦 Building $actor..."

    # Build the actor
    cargo build -p $actor --target wasm32-wasip1 --release

    # Create build directory
    mkdir -p actors/$actor/build

    # Sign the actor with wash (creates a signed .wasm)
    # Convert actor name for the WASM file (replace hyphens with underscores for Rust)
    local wasm_name=${actor//-/_}

    if command -v wash &> /dev/null; then
        echo "  🔏 Signing $actor with wash..."
        wash_cmd build --sign-only \
            --input target/wasm32-wasip1/release/${wasm_name}.wasm \
            --output actors/$actor/build/${actor}_s.wasm \
            --disable-keygen 2>/dev/null || {
            echo "  ⚠️  Signing failed, copying unsigned WASM..."
            cp target/wasm32-wasip1/release/${wasm_name}.wasm actors/$actor/build/${actor}_s.wasm
        }
    else
        echo "  ⚠️  wash not found, copying unsigned WASM..."
        cp target/wasm32-wasip1/release/${wasm_name}.wasm actors/$actor/build/${actor}_s.wasm
    fi

    echo "  ✅ $actor built successfully"
}

# =============================================================================
# Provider Building (Linux cross-compilation for K8s deployment)
# =============================================================================

touch_provider_source() {
    local dir_name=$1
    local package_name=$2
    local bin_name=${3:-$package_name}
    local candidates=(
        "providers/$dir_name/src/bin/${bin_name}.rs"
        "providers/$dir_name/src/${bin_name}.rs"
        "providers/$dir_name/src/wasmcloud_provider.rs"
        "providers/$dir_name/src/bin/${package_name}.rs"
        "providers/$dir_name/src/main.rs"
    )

    for path in "${candidates[@]}"; do
        if [ -f "$path" ]; then
            touch "$path"
            return 0
        fi
    done
}

# Build provider for Linux using musl (Alpine) - works for most providers
build_provider_linux_musl() {
    local package_name=$1
    local dir_name=$2
    local bin_name=${3:-$package_name}

    echo "  🐧 Cross-compiling $package_name for Linux (musl)..."

    # Create build directory
    mkdir -p providers/$dir_name/build

    # Touch the source file to trigger rebuild (avoids Docker cache issues)
    touch_provider_source "$dir_name" "$package_name" "$bin_name"

    if [ "${USE_ZIGBUILD}" = "true" ]; then
        if ! command -v zig >/dev/null 2>&1; then
            echo "  ❌ zig not found (install with: brew install zig)"
            return 1
        fi
        if ! command -v cargo-zigbuild >/dev/null 2>&1; then
            echo "  ❌ cargo-zigbuild not found (install with: cargo install cargo-zigbuild)"
            return 1
        fi
        CARGO_TARGET_DIR=target-k8s cargo zigbuild --release --target "${LINUX_MUSL_TARGET}" \
          -p "$package_name" --bin "$bin_name"
        cp "target-k8s/${LINUX_MUSL_TARGET}/release/$bin_name" \
          "providers/$dir_name/build/${package_name}-${LINUX_ARCH_LABEL}"
    else
        docker run --rm --platform "${DOCKER_PLATFORM}" \
          -e "CARGO_HOME=${CONTAINER_CARGO_HOME}" \
          -e "RUSTUP_HOME=${CONTAINER_RUSTUP_HOME}" \
          "${DOCKER_RUSTFLAGS_ENV[@]}" \
          -v "$PROJECT_ROOT:/project" \
          -w /project/apps/wasmcloud \
          rust:alpine sh -c "
            apk add --no-cache musl-dev openssl-dev openssl-libs-static pkgconfig g++ &&
            rustup toolchain install stable &&
            rustup default stable &&
            rustup target add ${LINUX_MUSL_TARGET} &&
            OPENSSL_STATIC=1 OPENSSL_LIB_DIR=/usr/lib OPENSSL_INCLUDE_DIR=/usr/include \
            CARGO_TARGET_DIR=target-k8s cargo build --release --target ${LINUX_MUSL_TARGET} \
              -p $package_name --bin $bin_name &&
            cp target-k8s/${LINUX_MUSL_TARGET}/release/$bin_name \
              providers/$dir_name/build/${package_name}-${LINUX_ARCH_LABEL}
          "
    fi

    echo "  ✅ $package_name cross-compiled for Linux"
}

# Build provider for Linux using glibc (Debian) - required for DuckDB extensions
build_provider_linux_glibc() {
    local package_name=$1
    local dir_name=$2
    local bin_name=${3:-$package_name}

    echo "  🐧 Cross-compiling $package_name for Linux (glibc - DuckDB compatible)..."

    # Create build directory
    mkdir -p providers/$dir_name/build

    # Touch the source file to trigger rebuild
    touch_provider_source "$dir_name" "$package_name" "$bin_name"

    if [ "${USE_ZIGBUILD}" = "true" ]; then
        if ! command -v zig >/dev/null 2>&1; then
            echo "  ❌ zig not found (install with: brew install zig)"
            return 1
        fi
        if ! command -v cargo-zigbuild >/dev/null 2>&1; then
            echo "  ❌ cargo-zigbuild not found (install with: cargo install cargo-zigbuild)"
            return 1
        fi
        CARGO_TARGET_DIR=target-k8s cargo zigbuild --release --target "${LINUX_GLIBC_TARGET}" \
          -p "$package_name" --bin "$bin_name"
        cp "target-k8s/${LINUX_GLIBC_TARGET}/release/$bin_name" \
          "providers/$dir_name/build/${package_name}-${LINUX_ARCH_LABEL}"
    else
        docker run --rm --platform "${DOCKER_PLATFORM}" \
          -e "CARGO_HOME=${CONTAINER_CARGO_HOME}" \
          -e "RUSTUP_HOME=${CONTAINER_RUSTUP_HOME}" \
          "${DOCKER_RUSTFLAGS_ENV[@]}" \
          -v "$PROJECT_ROOT:/project" \
          -w /project/apps/wasmcloud \
          rust:slim-bookworm sh -c "
            apt-get update && apt-get install -y pkg-config libssl-dev g++ &&
            rustup toolchain install stable &&
            rustup default stable &&
            rustup target add ${LINUX_GLIBC_TARGET} &&
            CARGO_TARGET_DIR=target-k8s cargo build --release --target ${LINUX_GLIBC_TARGET} \
              -p $package_name --bin $bin_name &&
            cp target-k8s/${LINUX_GLIBC_TARGET}/release/$bin_name \
              providers/$dir_name/build/${package_name}-${LINUX_ARCH_LABEL}
          "
    fi

    echo "  ✅ $package_name cross-compiled for Linux (glibc)"
}

# Build provider natively (for local macOS testing only - NOT for K8s deployment)
build_provider_native() {
    local package_name=$1
    local dir_name=$2
    local bin_name=${3:-$package_name}

    echo "  🍎 Building $package_name natively (macOS - NOT for K8s)..."

    # Create build directory
    mkdir -p providers/$dir_name/build

    if [ -n "${PROVIDER_RUSTFLAGS}" ]; then
        if ! RUSTFLAGS="${PROVIDER_RUSTFLAGS}" cargo build -p $package_name --release --bin "$bin_name"; then
            echo "  ❌ Failed to build $package_name"
            return 1
        fi
    else
        if ! cargo build -p $package_name --release --bin "$bin_name"; then
            echo "  ❌ Failed to build $package_name"
            return 1
        fi
    fi

    # Copy binary with consistent naming
    cp target/release/$bin_name providers/$dir_name/build/${package_name}-aarch64-macos

    echo "  ✅ $package_name built natively (macOS)"
}

# Create PAR file with correct Linux architecture
create_par_linux() {
    local package_name=$1
    local dir_name=$2
    local provider_name=${package_name%-provider}
    local binary_path="providers/$dir_name/build/${package_name}-${LINUX_ARCH_LABEL}"
    local arch="${LINUX_ARCH_LABEL}"

    # If BUILD_NATIVE=true, use macOS binary and architecture
    if [ "$BUILD_NATIVE" = "true" ]; then
        binary_path="providers/$dir_name/build/${package_name}-aarch64-macos"
        arch="aarch64-macos"
    fi

    if [ ! -f "$binary_path" ]; then
        echo "  ❌ Binary not found: $binary_path"
        return 1
    fi

    echo "  📦 Creating PAR archive for $provider_name (arch: $arch)..."

    if wash_cmd par create \
        --vendor ekko \
        --name $provider_name \
        --version $PROVIDER_VERSION \
        --arch $arch \
        --binary "$binary_path" \
        --destination providers/$dir_name/build/${provider_name}.par.gz \
        --compress 2>/dev/null; then

        echo "  ✅ PAR created: providers/$dir_name/build/${provider_name}.par.gz"

        # Verify architecture
        local par_arch=$(wash_cmd par inspect providers/$dir_name/build/${provider_name}.par.gz 2>/dev/null | grep -A1 "Supported Architecture" | tail -1 | tr -d ' ')
        echo "  🔍 PAR architecture: $par_arch"

        # Push to registry if enabled
        if [ "$PUSH_TO_REGISTRY" = "true" ]; then
            local push_registry="$REGISTRY"
            if [[ "$REGISTRY" == "host.docker.internal:"* ]]; then
                push_registry="localhost:${REGISTRY#host.docker.internal:}"
            fi
            echo "  ☁️  Pushing to registry: ${push_registry}/$provider_name:$PROVIDER_VERSION"
            if wash_cmd push \
                ${push_registry}/$provider_name:$PROVIDER_VERSION \
                providers/$dir_name/build/${provider_name}.par.gz \
                --insecure \
                --allow-latest 2>/dev/null; then
                echo "  ✅ Pushed to registry successfully"
            else
                echo "  ⚠️  Failed to push to registry"
            fi
        fi
    else
        echo "  ⚠️  PAR creation failed"
        return 1
    fi
}

# Main provider build function - orchestrates cross-compilation and PAR creation
build_provider() {
    local package_name=$1
    local dir_name=$2
    local build_type=${3:-musl}  # musl or glibc
    local bin_name=${4:-$package_name}

    echo "  📦 Building $package_name..."

    # Only build if Cargo.toml exists
    if [ ! -f "providers/$dir_name/Cargo.toml" ]; then
        echo "  ⏭️  Skipping $package_name (no Cargo.toml found)"
        return 0
    fi

    # Step 1: Build the binary
    if [ "$BUILD_NATIVE" = "true" ]; then
        build_provider_native "$package_name" "$dir_name" "$bin_name"
    elif [ "$build_type" = "glibc" ]; then
        build_provider_linux_glibc "$package_name" "$dir_name" "$bin_name"
    else
        build_provider_linux_musl "$package_name" "$dir_name" "$bin_name"
    fi

    # Step 2: Create PAR file (if wash is available and CREATE_PAR=true)
    if [ "$CREATE_PAR" = "true" ] && command -v wash &> /dev/null; then
        create_par_linux "$package_name" "$dir_name"
    else
        [ "$CREATE_PAR" = "false" ] && echo "  ⏭️  Skipping PAR creation (CREATE_PAR=false)"
        command -v wash &> /dev/null || echo "  ⚠️  wash not found, skipping PAR creation"
    fi

    echo "  ✅ $package_name build complete"
}

# =============================================================================
# Build Actors
# =============================================================================

if [ "$SKIP_ACTOR_BUILD" = "true" ]; then
    echo "⏭️  Skipping actor build (SKIP_ACTOR_BUILD=true)"
else
    echo "🔨 Building WasmCloud Actors..."
    echo ""

    build_actor "health-check"
    build_actor "eth_raw_transactions"
    build_actor "eth_process_transactions"
    build_actor "eth_transfers_processor"
    build_actor "eth_contract_creation_processor"
    build_actor "eth_contract_transaction_processor"
    build_actor "btc_raw_transactions"
    build_actor "sol_raw_transactions"
    build_actor "alerts-processor"
    build_actor "transaction-processor"
    build_actor "transaction-ducklake-writer"
    build_actor "notification-router"
    build_actor "abi-decoder"
fi

# =============================================================================
# Build Providers
# =============================================================================

if [ "$SKIP_PROVIDER_BUILD" = "true" ]; then
    echo ""
    echo "⏭️  Skipping provider build (SKIP_PROVIDER_BUILD=true)"
else
    echo ""
    echo "🔨 Building Providers (Linux PAR Archives)..."
    echo ""

    # Standard musl providers (most providers)
    MUSL_PROVIDERS=(
      "alert-scheduler-provider:alert-scheduler"
      "newheads-evm-provider:newheads-evm"
      "http-rpc-provider:http-rpc"
      "abi-decoder-provider:abi-decoder"
      "polars-eval-provider:polars-eval"
      "websocket-notification-provider:websocket-notification-provider:websocket-provider-wasmcloud"
      "email-notification-provider:email-notification-provider"
      "slack-notification-provider:slack-notification-provider"
      "telegram-notification-provider:telegram-notification-provider"
      "webhook-notification-provider:webhook-notification-provider"
    )

    # Glibc providers (DuckDB extensions require glibc, not musl)
    GLIBC_PROVIDERS=(
      "ducklake-write-provider:ducklake-write"
      "ducklake-read-provider:ducklake-read"
    )

    echo "Building musl providers..."
    for provider_spec in "${MUSL_PROVIDERS[@]}"; do
        IFS=':' read -r package_name dir_name bin_name <<< "$provider_spec"
        bin_name=${bin_name:-$package_name}
        build_provider "$package_name" "$dir_name" "musl" "$bin_name"
    done

    echo ""
    echo "Building glibc providers (DuckDB compatible)..."
    for provider_spec in "${GLIBC_PROVIDERS[@]}"; do
        IFS=':' read -r package_name dir_name bin_name <<< "$provider_spec"
        bin_name=${bin_name:-$package_name}
        build_provider "$package_name" "$dir_name" "glibc" "$bin_name"
    done
fi

# =============================================================================
# Build Summary
# =============================================================================

echo ""
echo "📊 Build Summary:"
echo "=================="
echo ""
echo "Actors (WASM):"
ls -lh actors/*/build/*.wasm 2>/dev/null | awk '{print $9, $5}' | column -t || echo "  No actors built"

echo ""
echo "Providers (Linux Binaries):"
ls -lh providers/*/build/*-${LINUX_ARCH_LABEL} 2>/dev/null | awk '{print $9, $5}' | column -t || echo "  No Linux binaries built"

if [ "$CREATE_PAR" = "true" ]; then
    echo ""
    echo "Provider Archives (PAR files):"
    ls -lh providers/*/build/*.par.gz 2>/dev/null | awk '{print $9, $5}' | column -t || echo "  No PAR files created"

    echo ""
    echo "PAR Architecture Verification:"
    for par in providers/*/build/*.par.gz; do
        if [ -f "$par" ]; then
            arch=$(wash_cmd par inspect "$par" 2>/dev/null | grep -A1 "Supported Architecture" | tail -1 | tr -d ' ')
            echo "  $(basename "$par"): $arch"
        fi
    done 2>/dev/null || echo "  No PAR files to verify"
fi

echo ""
echo "✨ Build complete! Actors and providers are ready for deployment."
echo ""
echo "Configuration:"
echo "  Environment File: ${ENV_FILE}"
echo "  Registry: $REGISTRY"
echo "  Provider Version: $PROVIDER_VERSION"
echo "  PAR Creation: $CREATE_PAR"
echo "  Push to Registry: $PUSH_TO_REGISTRY"
echo "  Build Native: $BUILD_NATIVE"
echo "  Provider Arch: ${LINUX_ARCH_LABEL}"
echo ""
echo "Usage Examples:"
echo "  # Standard build (Linux for K8s)"
echo "  ./build.sh"
echo ""
echo "  # Build with specific env file"
echo "  ENV_FILE=.env.production ./build.sh"
echo ""
echo "  # Skip provider build (actors only)"
echo "  SKIP_PROVIDER_BUILD=true ./build.sh"
echo ""
echo "  # Build and push to registry"
echo "  PUSH_TO_REGISTRY=true ./build.sh"
echo ""
echo "  # Native macOS build (for local testing only - NOT for K8s)"
echo "  BUILD_NATIVE=true ./build.sh"
