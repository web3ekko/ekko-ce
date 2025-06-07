# Makefile for API testing and development

.PHONY: help test test-unit test-integration test-migration test-coverage test-verbose clean install-deps check-deps

# Default target
help:
	@echo "Available targets:"
	@echo "  test              - Run all tests"
	@echo "  test-unit         - Run unit tests only"
	@echo "  test-integration  - Run integration tests only"
	@echo "  test-migration    - Run migration tests only"
	@echo "  test-coverage     - Run tests with coverage report"
	@echo "  test-verbose      - Run tests with verbose output"
	@echo "  test-parallel     - Run tests in parallel"
	@echo "  install-deps      - Install test dependencies"
	@echo "  check-deps        - Check if dependencies are installed"
	@echo "  clean             - Clean test artifacts"
	@echo "  list-tests        - List available test files"

# Install test dependencies
install-deps:
	pip install -r requirements.txt

# Check dependencies
check-deps:
	python scripts/run_tests.py --check-deps

# Run all tests
test:
	python scripts/run_tests.py

# Run unit tests only
test-unit:
	python scripts/run_tests.py --pattern "unit"

# Run integration tests only
test-integration:
	python scripts/run_tests.py --pattern "integration"

# Run migration tests only
test-migration:
	python scripts/run_tests.py --file test_migration.py

# Run tests with coverage
test-coverage:
	python scripts/run_tests.py --coverage

# Run tests with verbose output
test-verbose:
	python scripts/run_tests.py --verbose

# Run tests in parallel
test-parallel:
	python scripts/run_tests.py --parallel

# Run specific test file
test-user:
	python scripts/run_tests.py --file test_user_repository.py

test-wallet:
	python scripts/run_tests.py --file test_wallet_repository.py

test-alert:
	python scripts/run_tests.py --file test_alert_repository.py

test-balance:
	python scripts/run_tests.py --file test_wallet_balance_repository.py

# List available tests
list-tests:
	python scripts/run_tests.py --list

# Clean test artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf .coverage 2>/dev/null || true
	rm -rf /tmp/test_*.db 2>/dev/null || true

# Development helpers
dev-setup: install-deps
	@echo "Development environment setup complete"

# Quick test (fast subset)
test-quick:
	python scripts/run_tests.py --pattern "not slow"

# Test with Docker (if needed)
test-docker:
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Format code (if you have black installed)
format:
	black app/ tests/ scripts/ --line-length 100

# Lint code (if you have flake8 installed)
lint:
	flake8 app/ tests/ scripts/ --max-line-length 100

# Type check (if you have mypy installed)
typecheck:
	mypy app/ --ignore-missing-imports

# Run all quality checks
quality: format lint typecheck test

# Database migration test
test-db-migration:
	python scripts/test_migration.py

# Manual migration
migrate:
	python scripts/run_migration.py

# Check migration status
migration-status:
	python scripts/run_migration.py --check-only
