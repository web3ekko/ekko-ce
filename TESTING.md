# Testing Guide for Ekko Transactions API

This document provides comprehensive testing instructions for the transactions API implementation, covering both backend and frontend testing.

## 🏗️ **Architecture Overview**

The transactions system consists of:
- **Backend API** (FastAPI + DuckDB + MinIO)
- **Frontend Service** (TypeScript + React)
- **Integration Layer** (React Hooks + State Management)

## 🧪 **Backend API Testing**

### **Setup**

```bash
cd api
pip install -r requirements-test.txt
```

### **Running Tests**

```bash
# Run all tests
python run_tests.py

# Run specific test categories
python run_tests.py --unit              # Unit tests only
python run_tests.py --integration       # Integration tests only
python run_tests.py --api              # API endpoint tests only
python run_tests.py --transactions     # Transaction-specific tests only

# Run with coverage
python run_tests.py --coverage

# Run specific test file
python run_tests.py --file tests/test_transactions_api.py

# Run specific test function
python run_tests.py --file tests/test_transactions_api.py --function test_get_transactions_success

# Verbose output
python run_tests.py --verbose

# Skip slow tests
python run_tests.py --fast
```

### **Test Structure**

```
api/tests/
├── test_transactions_api.py      # API endpoint tests
├── test_duckdb_service.py        # DuckDB service tests
├── conftest.py                   # Test configuration
└── fixtures/                     # Test data fixtures
```

### **Key Test Cases**

#### **API Endpoints (`test_transactions_api.py`)**
- ✅ **GET /transactions** - Fetch with filters, pagination, sorting
- ✅ **GET /transactions/{hash}** - Single transaction retrieval
- ✅ **GET /transactions/stats** - Transaction statistics
- ✅ **Error handling** - Database errors, invalid parameters
- ✅ **Authentication** - User authorization
- ✅ **Validation** - Input parameter validation

#### **DuckDB Service (`test_duckdb_service.py`)**
- ✅ **Connection management** - Pool creation, cleanup
- ✅ **Query execution** - Parameterized queries, error handling
- ✅ **MinIO integration** - S3 configuration, file access
- ✅ **Performance** - Concurrent queries, connection reuse

## 🎯 **Frontend Testing**

### **Setup**

```bash
cd dashboard
yarn install
```

### **Running Tests**

```bash
# Run all tests
yarn vitest

# Run in watch mode
yarn vitest:watch

# Run with UI
yarn vitest:ui

# Run with coverage
yarn vitest:coverage

# Run specific test categories
yarn test:transactions    # Transaction-related tests
yarn test:api            # API service tests
yarn test:hooks          # React hooks tests
yarn test:integration    # Integration tests
```

### **Test Structure**

```
dashboard/src/
├── services/api/__tests__/
│   └── transactions.service.test.ts    # API service tests
├── hooks/__tests__/
│   └── useTransactions.test.ts         # React hook tests
└── pages/ekko/__tests__/
    └── Transactions.integration.test.tsx # Integration tests
```

### **Key Test Cases**

#### **API Service (`transactions.service.test.ts`)**
- ✅ **getTransactions()** - Query parameter handling, response parsing
- ✅ **getTransaction()** - Single transaction fetch
- ✅ **getTransactionStats()** - Statistics retrieval
- ✅ **exportTransactions()** - CSV export functionality
- ✅ **Error handling** - Network errors, API errors
- ✅ **URL encoding** - Special characters, arrays

#### **React Hook (`useTransactions.test.ts`)**
- ✅ **State management** - Loading, error, data states
- ✅ **Auto-refresh** - Interval-based updates
- ✅ **Pagination** - Load more functionality
- ✅ **Filtering** - Search, tabs, wallet filtering
- ✅ **Export** - CSV download handling
- ✅ **Error recovery** - Retry mechanisms

#### **Integration Tests (`Transactions.integration.test.tsx`)**
- ✅ **Page rendering** - Component mounting, data display
- ✅ **User interactions** - Search, filtering, pagination
- ✅ **State synchronization** - Store updates, real-time data
- ✅ **Error states** - Loading, error, empty states
- ✅ **Export workflow** - Full download process

## 🔧 **Test Configuration**

### **Backend (pytest.ini)**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
asyncio_mode = auto
addopts = 
    --cov=src
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    api: API endpoint tests
    transactions: Transaction-related tests
```

### **Frontend (vitest.config.ts)**
```typescript
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      reporter: ['text', 'html', 'json'],
      threshold: {
        global: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80
        }
      }
    }
  }
});
```

## 🚀 **Running Full Test Suite**

### **Backend**
```bash
cd api
python run_tests.py --coverage --verbose
```

### **Frontend**
```bash
cd dashboard
yarn vitest:coverage
```

## 📊 **Test Coverage Goals**

- **Backend**: 80%+ coverage
- **Frontend**: 80%+ coverage
- **Critical paths**: 95%+ coverage
  - Transaction fetching
  - Error handling
  - User interactions

## 🐛 **Debugging Tests**

### **Backend Debugging**
```bash
# Run with verbose output
python run_tests.py --verbose

# Run specific failing test
python run_tests.py --file tests/test_transactions_api.py --function test_get_transactions_success

# Use pytest directly for more control
python -m pytest tests/test_transactions_api.py::TestTransactionsAPI::test_get_transactions_success -v -s
```

### **Frontend Debugging**
```bash
# Run with UI for interactive debugging
yarn vitest:ui

# Run specific test file
yarn vitest src/services/api/__tests__/transactions.service.test.ts

# Run with verbose output
yarn vitest --reporter=verbose
```

## 🔄 **Continuous Integration**

### **GitHub Actions Example**
```yaml
name: Test Transactions API

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd api
          pip install -r requirements-test.txt
      - name: Run tests
        run: |
          cd api
          python run_tests.py --coverage

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: |
          cd dashboard
          yarn install
      - name: Run tests
        run: |
          cd dashboard
          yarn vitest:coverage
```

## 📝 **Test Data**

### **Mock Transactions**
- **Avalanche mainnet** transactions
- **Multiple transaction types** (send, receive, contract interaction)
- **Various statuses** (confirmed, pending, failed)
- **Different tokens** (AVAX, USDC.e, PNG, JOE)

### **Test Scenarios**
- ✅ **Happy path** - Normal transaction flow
- ✅ **Edge cases** - Empty results, large datasets
- ✅ **Error conditions** - Network failures, invalid data
- ✅ **Performance** - Large result sets, concurrent requests

## 🎯 **Next Steps**

1. **Run the test suite** to verify current implementation
2. **Add integration tests** with real DuckDB/MinIO setup
3. **Performance testing** with large datasets
4. **End-to-end testing** with Playwright/Cypress
5. **Load testing** for API endpoints

## 📚 **Resources**

- [pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
- [Testing Library](https://testing-library.com/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [DuckDB Testing](https://duckdb.org/docs/dev/testing)
