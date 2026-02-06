# Makefile for Newheads EVM Provider (WADM/PAR workflow)
# For Linux/K8s cross-compilation, use: apps/wasmcloud/build.sh

.PHONY: build par push test check format lint clean help

PROVIDER_NAME := newheads-evm
BINARY := newheads-evm-provider
VERSION ?= v1.0.0
REGISTRY ?= registry.kube-system.svc.cluster.local:80
WASH ?= wash

build:
	@echo "Building provider..."
	cargo build --release --bin $(BINARY)

par: build
	@echo "Creating PAR archive..."
	$(WASH) par create \
		--vendor ekko \
		--name $(PROVIDER_NAME) \
		--version $(VERSION) \
		--binary target/release/$(BINARY) \
		--destination target/release/$(PROVIDER_NAME).par.gz \
		--compress
	@echo "✅ PAR created: target/release/$(PROVIDER_NAME).par.gz"

push: par
	@echo "Pushing PAR to registry..."
	$(WASH) push \
		$(REGISTRY)/$(PROVIDER_NAME):$(VERSION) \
		target/release/$(PROVIDER_NAME).par.gz \
		--insecure \
		--allow-latest

clean:
	@echo "Cleaning build artifacts..."
	cargo clean
	rm -f target/release/*.par.gz

test:
	@echo "Running tests..."
	cargo test

check:
	@echo "Checking code..."
	cargo check --bin $(BINARY)

format:
	@echo "Formatting code..."
	cargo fmt

lint:
	@echo "Linting code..."
	cargo clippy -- -D warnings

help:
	@echo "Available targets:"
	@echo "  build   - Build provider binary"
	@echo "  par     - Create PAR archive"
	@echo "  push    - Push PAR to OCI registry"
	@echo "  clean   - Clean build artifacts"
	@echo "  test    - Run tests"
	@echo "  check   - Check code without building"
	@echo "  format  - Format code"
	@echo "  lint    - Lint code"
	@echo "  help    - Show this help"
