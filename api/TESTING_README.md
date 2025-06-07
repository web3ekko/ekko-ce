# 🧪 Testing Guide

This document describes the comprehensive testing setup for the API service, including unit tests for models and repository methods using testcontainers.

## 📋 Overview

The testing framework includes:

- **Unit Tests**: Model validation and repository CRUD operations
- **Integration Tests**: Database migration and cross-component functionality  
- **Testcontainers**: Isolated test environments with real NATS and DuckDB
- **Automated Setup**: Containers started at test beginning, deleted when done

## 🏗️ Test Architecture

### Test Structure

```
api/tests/
├── conftest.py                    # Test fixtures and configuration
├── test_user_repository.py        # User model and repository tests
├── test_wallet_repository.py      # Wallet model and repository tests
├── test_alert_repository.py       # Alert model and repository tests
├── test_wallet_balance_repository.py  # WalletBalance tests
└── test_migration.py              # Migration functionality tests
```

### Testcontainers Setup

The test suite uses testcontainers to provide:

- **NATS Container**: Real NATS server with JetStream for testing
- **Temporary DuckDB**: Isolated database for each test session
- **Automatic Cleanup**: Containers and databases removed after tests

## 🚀 Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install -r requirements.txt
```

Or use the Makefile:

```bash
make install-deps
```

### Quick Start

```bash
# Run all tests
make test

# Run with verbose output
make test-verbose

# Run with coverage report
make test-coverage

# Run tests in parallel
make test-parallel
```

### Specific Test Categories

```bash
# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run migration tests only
make test-migration
```

### Individual Test Files

```bash
# Test user functionality
make test-user

# Test wallet functionality
make test-wallet

# Test alert functionality
make test-alert

# Test wallet balance functionality
make test-balance
```

### Using the Test Runner Script

```bash
# Run all tests
python scripts/run_tests.py

# Run specific test pattern
python scripts/run_tests.py --pattern "user"

# Run specific test file
python scripts/run_tests.py --file test_user_repository.py

# Run with coverage
python scripts/run_tests.py --coverage --verbose

# List available tests
python scripts/run_tests.py --list

# Check dependencies
python scripts/run_tests.py --check-deps
```

## 📊 Test Coverage

### Model Tests

Each model is tested for:

- ✅ **Valid Creation**: Creating models with valid data
- ✅ **Default Values**: Testing default field values
- ✅ **Validation**: Testing field validation and constraints
- ✅ **Required Fields**: Testing missing required fields

### Repository Tests

Each repository is tested for:

- ✅ **Create**: Adding new entities to database
- ✅ **Read**: Retrieving entities by ID and other criteria
- ✅ **Update**: Modifying existing entities
- ✅ **Delete**: Removing entities from database
- ✅ **List**: Querying multiple entities with filters
- ✅ **Search**: Text-based searching functionality
- ✅ **Statistics**: Aggregate data and reporting

### Migration Tests

Migration functionality is tested for:

- ✅ **Schema Creation**: Database table initialization
- ✅ **Data Migration**: JetStream to DuckDB data transfer
- ✅ **Data Integrity**: Foreign key constraints and validation
- ✅ **Error Handling**: Invalid data and edge cases
- ✅ **Backup/Restore**: Data backup and recovery

## 🔧 Test Configuration

### Environment Variables

Tests use these environment variables:

```bash
TEST_MODE=true                    # Enable test mode
TEST_NATS_URL=nats://localhost:4222  # NATS container URL
TEST_DUCKDB_PATH=/tmp/test_*.db   # Temporary database path
```

### Pytest Configuration

Key pytest settings in `pytest.ini`:

```ini
[tool:pytest]
asyncio_mode = auto              # Automatic asyncio support
testpaths = tests               # Test directory
timeout = 300                   # Test timeout (5 minutes)
markers =                       # Test markers for categorization
    unit: Unit tests
    integration: Integration tests
    database: Tests requiring database
    jetstream: Tests requiring JetStream
```

### Test Fixtures

Key fixtures in `conftest.py`:

- `nats_container`: NATS testcontainer with JetStream
- `test_database`: Temporary DuckDB database
- `db_schema`: Initialized database schema
- `user_repository`: UserRepository with test setup
- `wallet_repository`: WalletRepository with test setup
- `alert_repository`: AlertRepository with test setup
- `wallet_balance_repository`: WalletBalanceRepository with test setup

## 📝 Writing New Tests

### Model Tests

```python
class TestMyModel:
    """Test MyModel validation."""
    
    def test_model_creation(self):
        """Test creating model with valid data."""
        data = {"id": str(uuid.uuid4()), "name": "Test"}
        model = MyModel(**data)
        assert model.id == data["id"]
        assert model.name == data["name"]
    
    def test_model_validation(self):
        """Test model validation."""
        with pytest.raises(ValueError):
            MyModel(id="invalid")
```

### Repository Tests

```python
class TestMyRepository:
    """Test MyRepository CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create(self, my_repository: MyRepository):
        """Test creating entity."""
        entity = MyModel(id=str(uuid.uuid4()), name="Test")
        created = await my_repository.create(entity)
        assert created.id == entity.id
    
    @pytest.mark.asyncio
    async def test_get_by_id(self, my_repository: MyRepository):
        """Test retrieving entity by ID."""
        # Create entity first
        entity = MyModel(id=str(uuid.uuid4()), name="Test")
        created = await my_repository.create(entity)
        
        # Retrieve entity
        retrieved = await my_repository.get_by_id(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
```

### Test Markers

Use markers to categorize tests:

```python
@pytest.mark.unit
def test_model_validation():
    """Unit test for model validation."""
    pass

@pytest.mark.integration
@pytest.mark.database
async def test_repository_integration():
    """Integration test requiring database."""
    pass

@pytest.mark.slow
async def test_large_dataset():
    """Slow test with large dataset."""
    pass
```

## 🐛 Debugging Tests

### Verbose Output

```bash
# Run with detailed output
make test-verbose

# Run specific test with debugging
python -m pytest tests/test_user_repository.py::TestUserRepository::test_create_user -v -s
```

### Test Isolation

Each test runs in isolation with:

- Fresh database schema
- Clean JetStream buckets
- Separate container instances

### Common Issues

1. **Container Startup Failures**
   - Check Docker is running
   - Verify port availability
   - Check container logs

2. **Database Connection Issues**
   - Verify DuckDB dependency
   - Check temporary file permissions
   - Review database path configuration

3. **Async Test Issues**
   - Ensure `@pytest.mark.asyncio` decorator
   - Check asyncio mode in pytest.ini
   - Verify fixture dependencies

## 📈 Performance Testing

### Benchmarking

```bash
# Run performance tests
python scripts/run_tests.py --pattern "performance"

# Profile test execution
python -m pytest --profile tests/
```

### Load Testing

```bash
# Test with large datasets
python scripts/run_tests.py --pattern "load"

# Parallel execution
make test-parallel
```

## 🔄 Continuous Integration

### GitHub Actions

Example workflow for CI:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: make test-coverage
```

### Docker Testing

```bash
# Run tests in Docker environment
make test-docker
```

## 📚 Best Practices

### Test Organization

1. **One test class per model/repository**
2. **Descriptive test method names**
3. **Arrange-Act-Assert pattern**
4. **Independent test cases**

### Data Management

1. **Use unique IDs for test data**
2. **Clean up after each test**
3. **Avoid hardcoded values**
4. **Use factories for test data**

### Assertions

1. **Test both positive and negative cases**
2. **Verify all important fields**
3. **Check error conditions**
4. **Test edge cases**

## 🛠️ Maintenance

### Updating Tests

When adding new models or repositories:

1. Create corresponding test files
2. Add fixtures to `conftest.py`
3. Update test markers and categories
4. Add Makefile targets if needed

### Dependency Updates

```bash
# Check for outdated packages
pip list --outdated

# Update test dependencies
pip install --upgrade pytest pytest-asyncio testcontainers

# Verify tests still pass
make test
```

This comprehensive testing setup ensures reliable, maintainable code with high confidence in the database migration and repository functionality.
