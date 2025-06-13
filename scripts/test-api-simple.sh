#!/bin/bash

# 🧪 Simple API Test for Transaction Flow
# Tests API endpoints with sample data

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
API_URL="http://localhost:8000"

echo "🧪 Simple API Transaction Test"
echo "=============================="

# Function to wait for service
wait_for_service() {
    local url=$1
    local service_name=$2
    local timeout=${3:-60}
    local counter=0
    
    print_status "Waiting for $service_name to be ready..."
    
    while ! curl -f "$url" > /dev/null 2>&1; do
        if [ $counter -ge $timeout ]; then
            print_error "$service_name failed to start within $timeout seconds"
            return 1
        fi
        echo -n "."
        sleep 2
        counter=$((counter + 2))
    done
    echo ""
    print_success "$service_name is ready"
}

# Start infrastructure and API
print_status "Starting services..."
docker-compose up -d minio nats redis api

# Wait for API
wait_for_service "$API_URL/health" "API" 120

# Test basic API health
print_status "Testing API health..."
response=$(curl -s "$API_URL/health")
if echo "$response" | grep -q "healthy"; then
    print_success "API health check passed"
else
    print_error "API health check failed"
    echo "Response: $response"
    exit 1
fi

# Test API docs
print_status "Testing API documentation..."
if curl -f "$API_URL/docs" > /dev/null 2>&1; then
    print_success "API documentation is accessible"
else
    print_error "API documentation is not accessible"
fi

# Test transactions endpoint (without auth for now)
print_status "Testing transactions endpoint..."
response=$(curl -s "$API_URL/transactions" || echo "FAILED")

if [ "$response" = "FAILED" ]; then
    print_error "Transactions endpoint failed to respond"
else
    print_success "Transactions endpoint responded"
    echo "Response preview: $(echo "$response" | head -c 200)..."
fi

# Test networks endpoint
print_status "Testing networks endpoint..."
response=$(curl -s "$API_URL/transactions/networks" || echo "FAILED")

if [ "$response" = "FAILED" ]; then
    print_error "Networks endpoint failed to respond"
else
    print_success "Networks endpoint responded"
    echo "Response preview: $(echo "$response" | head -c 200)..."
fi

print_success "Simple API test completed!"
echo ""
echo "🌐 Access Points:"
echo "- API Health: $API_URL/health"
echo "- API Docs: $API_URL/docs"
echo "- Transactions: $API_URL/transactions"
echo "- Networks: $API_URL/transactions/networks"
echo ""
echo "📊 Next Steps:"
echo "1. Check API logs: docker-compose logs api"
echo "2. Access API docs at $API_URL/docs"
echo "3. Test endpoints manually with curl or Postman"
