# Django Admin Test Suite

This directory contains comprehensive unit tests for the Django admin interface, derived from PRDs and executed with testcontainers for integration testing.

## Test Structure

The test suite is organized by admin functionality:

### 1. Blockchain Node Management (`test_blockchain_node_management.py`)
- Tests for blockchain node CRUD operations
- Health check monitoring and status displays
- Primary node validation and failover
- Bulk operations (enable/disable/health checks)
- NATS export functionality for wasmCloud integration

### 2. NATS Control & Monitoring (`test_nats_control_monitoring.py`)
- wasmCloud actor management via NATS
- Stream and consumer configuration
- Dead letter queue management
- Command status tracking
- Retry and recovery operations

### 3. Real-time Dashboard (`test_realtime_dashboard.py`)
- Metric visualization and anomaly detection
- WebSocket connection monitoring
- Dashboard widget management
- System event administration
- Performance monitoring integration

### 4. Infrastructure Monitoring (`test_infrastructure_monitoring.py`)
- Redis metrics and key pattern analysis
- DuckLake table management
- wasmCloud actor and provider monitoring
- Component health status tracking
- Infrastructure alert administration

### 5. Audit & Compliance (`test_audit_compliance.py`)
- Audit log integrity verification
- Compliance report generation
- Data retention policy management
- Access pattern analysis
- High-risk operation detection

### 6. Alert System Administration (`test_alert_system_administration.py`)
- Alert template management (pending implementation)
- Performance monitoring
- Quota management
- NLP pipeline monitoring
- Debugging tools
- Emergency controls

## Test Configuration

### Using Testcontainers

All tests use testcontainers for integration testing with real services:
- PostgreSQL for database operations
- Redis for caching and metrics
- NATS for messaging (when implemented)

The `conftest.py` file provides fixtures for:
- `postgres_container`: PostgreSQL instance
- `redis_container`: Redis instance
- `db`: Database with migrations
- `admin_user`: Superuser for admin access
- `admin_client`: Authenticated admin client

### Test Factories

The `factories.py` file provides Factory Boy factories for all models:
- `UserFactory`: Create test users with admin trait
- `AlertFactory`: Create alerts with various states
- `BlockchainNodeFactory`: Create blockchain nodes
- `InfrastructureComponentFactory`: Create infrastructure components
- `AuditLogFactory`: Create audit logs
- And many more...

### Shared Fixtures

The `fixtures.py` file provides common test fixtures:
- `admin_user`: Superuser for tests
- `admin_client`: Authenticated client
- `test_data`: Basic test dataset
- `large_dataset`: Performance testing data

## Running Tests

### All Admin Tests
```bash
pytest tests/admin/ -v
```

### Specific Test Categories
```bash
# Blockchain node admin tests
pytest tests/admin/ -m admin_blockchain

# NATS control admin tests
pytest tests/admin/ -m admin_nats

# Dashboard admin tests
pytest tests/admin/ -m admin_dashboard

# Infrastructure admin tests
pytest tests/admin/ -m admin_infrastructure

# Audit compliance admin tests
pytest tests/admin/ -m admin_audit

# Alert system admin tests
pytest tests/admin/ -m admin_alerts
```

### With Coverage
```bash
pytest tests/admin/ --cov=app.admin --cov-report=html
```

### Using the Test Script
```bash
./run_admin_tests.sh
```

## Test Markers

Tests are marked with pytest markers for easy filtering:
- `@pytest.mark.admin`: All admin tests
- `@pytest.mark.admin_blockchain`: Blockchain admin tests
- `@pytest.mark.admin_nats`: NATS admin tests
- `@pytest.mark.admin_dashboard`: Dashboard admin tests
- `@pytest.mark.admin_infrastructure`: Infrastructure admin tests
- `@pytest.mark.admin_audit`: Audit admin tests
- `@pytest.mark.admin_alerts`: Alert admin tests

## Pending Implementations

Some tests are marked with `@pytest.mark.skip` because the corresponding admin features are not yet implemented:
- Alert template administration
- NLP monitoring dashboard
- Emergency alert controls
- Performance dashboard views
- Notification monitoring

These can be enabled once the admin features are implemented.

## Dependencies

Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
pip install -r requirements-test.txt
```

Key testing dependencies:
- pytest
- pytest-django
- testcontainers
- factory-boy
- faker
