# Ekko wasmCloud Application Makefile

.PHONY: help build build-release test clean deploy-dev deploy-staging deploy-prod wash-up wash-down

# Default target
help:
	@echo "Ekko wasmCloud Application Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  build          - Build all actors and providers for development"
	@echo "  build-release  - Build all actors and providers for production"
	@echo "  test           - Run all tests"
	@echo "  test-integration - Run integration tests"
	@echo "  clean          - Clean all build artifacts"
	@echo "  wash-up        - Start local wasmCloud host"
	@echo "  wash-down      - Stop local wasmCloud host"
	@echo "  deploy-dev     - Deploy to development environment"
	@echo "  deploy-staging - Deploy to staging environment"
	@echo "  deploy-prod    - Deploy to production environment"
	@echo "  docker-deps    - Start local dependencies (NATS, Redis)"
	@echo "  docker-down    - Stop local dependencies"

# Build targets
build:
	@echo "Building all components for development..."
	cargo build --target wasm32-wasip1
	@echo "✅ Development build complete"

build-release:
	@echo "Building all components for production..."
	cargo build --target wasm32-wasip1 --release
	@echo "✅ Production build complete"

# Test targets
test:
	@echo "Running unit tests..."
	cargo test
	@echo "✅ Unit tests complete"

test-integration:
	@echo "Running integration tests..."
	cargo test --test '*' --features integration-tests
	@echo "✅ Integration tests complete"

# Clean target
clean:
	@echo "Cleaning build artifacts..."
	cargo clean
	rm -rf target/
	@echo "✅ Clean complete"

# Local development dependencies
docker-deps:
	@echo "Starting local dependencies..."
	docker-compose -f ../docker-compose.dev.yml up -d nats redis minio minio-setup
	@echo "✅ Dependencies started"
	@echo "   - NATS: nats://localhost:4222"
	@echo "   - Redis: redis://localhost:6379"
	@echo "   - MinIO: http://localhost:9000 (admin/minioadmin)"
	@echo "   - MinIO Console: http://localhost:9001"

docker-down:
	@echo "Stopping local dependencies..."
	docker-compose -f ../docker-compose.dev.yml down
	@echo "✅ Dependencies stopped"

docker-deps-full:
	@echo "Starting all dependencies including monitoring..."
	docker-compose -f ../docker-compose.dev.yml --profile monitoring up -d
	@echo "✅ All dependencies started"
	@echo "   - NATS: nats://localhost:4222"
	@echo "   - Redis: redis://localhost:6379"
	@echo "   - MinIO: http://localhost:9000"
	@echo "   - PostgreSQL: postgresql://ekko:ekko_dev_password@localhost:5432/ekko"
	@echo "   - Prometheus: http://localhost:9090"
	@echo "   - Grafana: http://localhost:3000 (admin/admin)"

# wasmCloud host management
wash-up:
	@echo "Starting local wasmCloud host..."
	wash up --detached
	@echo "✅ wasmCloud host started"

wash-down:
	@echo "Stopping local wasmCloud host..."
	wash down
	@echo "✅ wasmCloud host stopped"

# Deployment targets
deploy-dev: build
	@echo "Deploying to development environment..."
	wash app deploy manifests/dev.yaml
	@echo "✅ Development deployment complete"

deploy-staging: build-release
	@echo "Deploying to staging environment..."
	wash app deploy manifests/staging.yaml
	@echo "✅ Staging deployment complete"

deploy-prod: build-release
	@echo "Deploying to production environment..."
	@echo "⚠️  Production deployment requires manual approval"
	@read -p "Are you sure you want to deploy to production? (y/N): " confirm && \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		wash app deploy manifests/production.yaml; \
		echo "✅ Production deployment complete"; \
	else \
		echo "❌ Production deployment cancelled"; \
	fi

# Development workflow
dev: docker-deps wash-up deploy-dev
	@echo "🚀 Development environment ready!"
	@echo "   - NATS: nats://localhost:4222"
	@echo "   - Redis: redis://localhost:6379"
	@echo "   - wasmCloud: http://localhost:4000"

dev-down: wash-down docker-down
	@echo "🛑 Development environment stopped"

# Build individual components
build-actors:
	@echo "Building all actors..."
	@for actor in actors/*/; do \
		if [ -f "$$actor/Cargo.toml" ]; then \
			echo "Building $$actor..."; \
			cd "$$actor" && cargo build --target wasm32-wasip1 && cd ../..; \
		fi \
	done
	@echo "✅ All actors built"

build-providers:
	@echo "Building all providers..."
	@for provider in providers/*/; do \
		if [ -f "$$provider/Cargo.toml" ]; then \
			echo "Building $$provider..."; \
			cd "$$provider" && cargo build --target wasm32-wasip1 && cd ../..; \
		fi \
	done
	@echo "✅ All providers built"

# Linting and formatting
lint:
	@echo "Running linter..."
	cargo clippy --all-targets --all-features -- -D warnings
	@echo "✅ Linting complete"

fmt:
	@echo "Formatting code..."
	cargo fmt --all
	@echo "✅ Formatting complete"

check: fmt lint test
	@echo "✅ All checks passed"

# Documentation
docs:
	@echo "Building documentation..."
	cargo doc --no-deps --open
	@echo "✅ Documentation built"

# Monitoring and debugging
logs:
	@echo "Showing wasmCloud logs..."
	wash ctl get logs

status:
	@echo "Checking wasmCloud status..."
	wash ctl get hosts
	wash ctl get actors
	wash ctl get providers

# Container builds (for production)
build-containers:
	@echo "Building container images..."
	docker build -t ghcr.io/ekko-zone/newheads-provider:latest providers/newheads/
	@for actor in actors/*/; do \
		if [ -f "$$actor/Dockerfile" ]; then \
			actor_name=$$(basename "$$actor"); \
			docker build -t "ghcr.io/ekko-zone/$$actor_name:latest" "$$actor/"; \
		fi \
	done
	@echo "✅ Container images built"

push-containers:
	@echo "Pushing container images..."
	docker push ghcr.io/ekko-zone/newheads-provider:latest
	@for actor in actors/*/; do \
		if [ -f "$$actor/Dockerfile" ]; then \
			actor_name=$$(basename "$$actor"); \
			docker push "ghcr.io/ekko-zone/$$actor_name:latest"; \
		fi \
	done
	@echo "✅ Container images pushed"

# Install dependencies
install-deps:
	@echo "Installing dependencies..."
	rustup target add wasm32-wasip1
	cargo install wash-cli
	@echo "✅ Dependencies installed"

# Setup development environment
setup: install-deps
	@echo "Setting up development environment..."
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "❌ Docker is required but not installed"; \
		exit 1; \
	fi
	@if ! command -v wash >/dev/null 2>&1; then \
		echo "❌ wash CLI is required but not installed"; \
		exit 1; \
	fi
	@echo "✅ Development environment setup complete"
