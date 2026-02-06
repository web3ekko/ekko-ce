# Ekko API - Docker Build and Deployment Makefile

# Variables
IMAGE_NAME := ekko/ekko-api
IMAGE_TAG := $(shell git rev-parse --short HEAD)
LATEST_TAG := latest
REGISTRY := ghcr.io/ekko-zone
NAMESPACE := ekko
HELM_CHART := ./helm/ekko-api

# Default target
.PHONY: help
help: ## Show this help message
	@echo "Ekko API - Docker Build and Deployment"
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development targets
.PHONY: dev-setup
dev-setup: ## Setup development environment
	@echo "Setting up development environment..."
	python -m venv venv-django
	./venv-django/bin/pip install --upgrade pip
	./venv-django/bin/pip install -r requirements.txt
	@echo "✅ Development environment ready"

.PHONY: dev-run
dev-run: ## Run development server
	@echo "Starting development server..."
	./venv-django/bin/python manage.py runserver 0.0.0.0:8000

.PHONY: dev-migrate
dev-migrate: ## Run database migrations
	@echo "Running database migrations..."
	./venv-django/bin/python manage.py migrate

.PHONY: dev-test
dev-test: ## Run tests
	@echo "Running tests..."
	./venv-django/bin/pytest -v

# Docker targets
.PHONY: docker-build
docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(IMAGE_NAME):$(LATEST_TAG)
	@echo "✅ Docker image built: $(IMAGE_NAME):$(IMAGE_TAG)"

.PHONY: docker-build-dev
docker-build-dev: ## Build Docker image for development
	@echo "Building development Docker image..."
	docker build -t $(IMAGE_NAME):dev .
	@echo "✅ Development Docker image built: $(IMAGE_NAME):dev"

.PHONY: docker-push
docker-push: docker-build ## Push Docker image to registry
	@echo "Pushing Docker image to registry..."
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(IMAGE_NAME):$(LATEST_TAG) $(REGISTRY)/$(IMAGE_NAME):$(LATEST_TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(LATEST_TAG)
	@echo "✅ Docker image pushed: $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)"

.PHONY: docker-run
docker-run: ## Run Docker container locally
	@echo "Running Docker container..."
	docker-compose up -d
	@echo "✅ Docker container running at http://localhost:8000"

.PHONY: docker-stop
docker-stop: ## Stop Docker container
	@echo "Stopping Docker container..."
	docker-compose down
	@echo "✅ Docker container stopped"

.PHONY: docker-logs
docker-logs: ## Show Docker container logs
	docker-compose logs -f ekko-api

# Kubernetes/Helm targets
.PHONY: helm-lint
helm-lint: ## Lint Helm chart
	@echo "Linting Helm chart..."
	helm lint $(HELM_CHART)
	@echo "✅ Helm chart linted successfully"

.PHONY: helm-template
helm-template: ## Generate Kubernetes manifests from Helm chart
	@echo "Generating Kubernetes manifests..."
	helm template ekko-api $(HELM_CHART) --values $(HELM_CHART)/values-dev.yaml
	@echo "✅ Kubernetes manifests generated"

.PHONY: helm-install-dev
helm-install-dev: ## Install Helm chart in development
	@echo "Installing Helm chart in development..."
	helm upgrade --install ekko-api-dev $(HELM_CHART) \
		--namespace $(NAMESPACE)-dev \
		--create-namespace \
		--values $(HELM_CHART)/values-dev.yaml \
		--set image.tag=$(IMAGE_TAG)
	@echo "✅ Helm chart installed in development"

.PHONY: helm-install-prod
helm-install-prod: ## Install Helm chart in production
	@echo "Installing Helm chart in production..."
	@read -p "Are you sure you want to deploy to production? (y/N): " confirm && \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		helm upgrade --install ekko-api $(HELM_CHART) \
			--namespace $(NAMESPACE) \
			--create-namespace \
			--values $(HELM_CHART)/values-prod.yaml \
			--set image.tag=$(IMAGE_TAG); \
		echo "✅ Helm chart installed in production"; \
	else \
		echo "❌ Production deployment cancelled"; \
	fi

.PHONY: helm-uninstall-dev
helm-uninstall-dev: ## Uninstall Helm chart from development
	@echo "Uninstalling Helm chart from development..."
	helm uninstall ekko-api-dev --namespace $(NAMESPACE)-dev
	@echo "✅ Helm chart uninstalled from development"

.PHONY: helm-status
helm-status: ## Show Helm deployment status
	@echo "Helm deployment status:"
	helm list --all-namespaces | grep ekko-api

# Deployment pipeline targets
.PHONY: deploy-dev
deploy-dev: docker-build helm-install-dev ## Build and deploy to development
	@echo "✅ Deployed to development environment"

.PHONY: deploy-prod
deploy-prod: docker-build docker-push helm-install-prod ## Build, push and deploy to production
	@echo "✅ Deployed to production environment"

# Utility targets
.PHONY: clean
clean: ## Clean up Docker images and containers
	@echo "Cleaning up Docker resources..."
	docker-compose down --volumes --remove-orphans
	docker rmi $(IMAGE_NAME):$(IMAGE_TAG) $(IMAGE_NAME):$(LATEST_TAG) 2>/dev/null || true
	docker system prune -f
	@echo "✅ Docker resources cleaned up"

.PHONY: logs-dev
logs-dev: ## Show development logs
	kubectl logs -f deployment/ekko-api-dev -n $(NAMESPACE)-dev

.PHONY: logs-prod
logs-prod: ## Show production logs
	kubectl logs -f deployment/ekko-api -n $(NAMESPACE)

.PHONY: shell-dev
shell-dev: ## Get shell access to development pod
	kubectl exec -it deployment/ekko-api-dev -n $(NAMESPACE)-dev -- /bin/bash

.PHONY: port-forward-dev
port-forward-dev: ## Port forward development service
	kubectl port-forward service/ekko-api-dev 8000:8000 -n $(NAMESPACE)-dev

.PHONY: health-check
health-check: ## Check application health
	@echo "Checking application health..."
	curl -f http://localhost:8000/health/ || echo "Health check failed"

# Database management
.PHONY: db-migrate
db-migrate: ## Run database migrations in Kubernetes
	kubectl exec deployment/ekko-api -n $(NAMESPACE) -- python manage.py migrate

.PHONY: db-shell
db-shell: ## Access database shell
	kubectl exec -it deployment/ekko-api -n $(NAMESPACE) -- python manage.py dbshell

# Security scanning
.PHONY: security-scan
security-scan: ## Run security scan on Docker image
	@echo "Running security scan..."
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
		aquasec/trivy image $(IMAGE_NAME):$(IMAGE_TAG)

# CI/CD helpers
.PHONY: ci-build
ci-build: docker-build helm-lint ## CI build pipeline
	@echo "✅ CI build completed"

.PHONY: ci-test
ci-test: dev-test security-scan ## CI test pipeline
	@echo "✅ CI tests completed"

.PHONY: version
version: ## Show current version information
	@echo "Image Tag: $(IMAGE_TAG)"
	@echo "Latest Tag: $(LATEST_TAG)"
	@echo "Registry: $(REGISTRY)"
	@echo "Namespace: $(NAMESPACE)"
