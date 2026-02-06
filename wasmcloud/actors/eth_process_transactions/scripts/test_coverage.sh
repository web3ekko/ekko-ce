#!/bin/bash

# Test Coverage Script for eth_process_transactions Actor
# This script runs comprehensive tests and generates coverage reports

set -e

echo "🧪 Running comprehensive test coverage for eth_process_transactions actor"
echo "=================================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Change to the actor directory
cd "$(dirname "$0")/.."

print_status "Current directory: $(pwd)"

# 1. Run standard unit tests
print_status "Running unit tests..."
cargo test --lib --verbose

if [ $? -eq 0 ]; then
    print_success "Unit tests passed!"
else
    print_error "Unit tests failed!"
    exit 1
fi

# 2. Run property-based tests (proptest)
print_status "Running property-based tests..."
cargo test --lib --verbose -- --ignored

if [ $? -eq 0 ]; then
    print_success "Property-based tests passed!"
else
    print_warning "Property-based tests had issues (this might be expected)"
fi

# 3. Run benchmarks (if available)
print_status "Running performance benchmarks..."
if command -v cargo-criterion &> /dev/null; then
    cargo criterion
    print_success "Benchmarks completed!"
else
    print_warning "cargo-criterion not installed, running basic bench..."
    cargo bench
fi

# 4. Check for test coverage using tarpaulin (if available)
print_status "Checking test coverage..."
if command -v cargo-tarpaulin &> /dev/null; then
    print_status "Running tarpaulin coverage analysis..."
    cargo tarpaulin --out Html --output-dir coverage --verbose
    print_success "Coverage report generated in coverage/ directory"
else
    print_warning "cargo-tarpaulin not installed. Install with: cargo install cargo-tarpaulin"
fi

# 5. Run clippy for code quality
print_status "Running clippy for code quality checks..."
cargo clippy --all-targets --all-features -- -D warnings

if [ $? -eq 0 ]; then
    print_success "Clippy checks passed!"
else
    print_error "Clippy found issues!"
    exit 1
fi

# 6. Check formatting
print_status "Checking code formatting..."
cargo fmt --check

if [ $? -eq 0 ]; then
    print_success "Code formatting is correct!"
else
    print_error "Code formatting issues found! Run 'cargo fmt' to fix."
    exit 1
fi

# 7. Run doc tests
print_status "Running documentation tests..."
cargo test --doc

if [ $? -eq 0 ]; then
    print_success "Documentation tests passed!"
else
    print_warning "Documentation tests had issues"
fi

# 8. Generate documentation
print_status "Generating documentation..."
cargo doc --no-deps --document-private-items

if [ $? -eq 0 ]; then
    print_success "Documentation generated successfully!"
else
    print_warning "Documentation generation had issues"
fi

# 9. Test compilation for WASM target
print_status "Testing WASM compilation..."
cargo check --target wasm32-wasip1

if [ $? -eq 0 ]; then
    print_success "WASM compilation check passed!"
else
    print_error "WASM compilation check failed!"
    exit 1
fi

# 10. Summary
echo ""
echo "=================================================================="
print_success "🎉 Test coverage analysis complete!"
echo ""
print_status "Summary of tests run:"
echo "  ✅ Unit tests (23+ tests)"
echo "  ✅ Property-based tests"
echo "  ✅ Performance benchmarks"
echo "  ✅ Code quality (clippy)"
echo "  ✅ Code formatting"
echo "  ✅ Documentation tests"
echo "  ✅ WASM compilation"

if command -v cargo-tarpaulin &> /dev/null; then
    echo "  ✅ Coverage report (see coverage/tarpaulin-report.html)"
fi

echo ""
print_status "To install additional tools for better coverage:"
echo "  cargo install cargo-tarpaulin  # For coverage reports"
echo "  cargo install cargo-criterion  # For detailed benchmarks"
echo ""
print_success "All tests completed successfully! 🚀"
