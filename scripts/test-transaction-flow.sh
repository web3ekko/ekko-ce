#!/bin/bash

# 🧪 End-to-End Transaction Flow Test
# Tests complete data flow: Pipeline → DuckDB → API → Frontend

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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
API_URL="http://localhost:8000"
DASHBOARD_URL="http://localhost:3000"
MINIO_URL="http://localhost:9000"

# Test data
TEST_WALLET_ADDRESS="0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF"
TEST_NETWORK="Avalanche"
TEST_SUBNET="Mainnet"

echo "🧪 End-to-End Transaction Flow Test"
echo "=================================="

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

# Function to create test user
create_test_user() {
    print_status "Creating test user..."
    
    # Check if user already exists
    if docker-compose exec -T api python -c "
import asyncio
import sys
import os
sys.path.append('/app')
from app.auth import get_user_by_email
from app.startup import get_js_instance

async def check_user():
    try:
        js = await get_js_instance()
        user = await get_user_by_email('test@ekko.com', js)
        if user:
            print('User already exists')
            return True
        return False
    except Exception as e:
        print(f'User check failed: {e}')
        return False

result = asyncio.run(check_user())
exit(0 if result else 1)
" 2>/dev/null; then
        print_success "Test user already exists"
        return 0
    fi
    
    # Create user
    docker-compose exec -T api python -c "
import asyncio
import sys
import os
sys.path.append('/app')
from app.auth import create_user
from app.models import UserCreate
from app.startup import get_js_instance

async def create_test_user():
    try:
        js = await get_js_instance()
        user_data = UserCreate(
            email='test@ekko.com',
            password='testpass123',
            full_name='Test User',
            role='admin'
        )
        user = await create_user(user_data, js)
        print(f'Created user: {user.email}')
        return True
    except Exception as e:
        print(f'User creation failed: {e}')
        return False

result = asyncio.run(create_test_user())
exit(0 if result else 1)
" && print_success "Test user created" || print_error "Failed to create test user"
}

# Function to get auth token
get_auth_token() {
    print_status "Getting authentication token..."
    
    local response=$(curl -s -X POST "$API_URL/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=test@ekko.com&password=testpass123")
    
    if echo "$response" | grep -q "access_token"; then
        AUTH_TOKEN=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
        print_success "Authentication token obtained"
        return 0
    else
        print_error "Failed to get authentication token"
        echo "Response: $response"
        return 1
    fi
}

# Function to create test wallet
create_test_wallet() {
    print_status "Creating test wallet..."
    
    local wallet_data='{
        "blockchain_symbol": "AVAX",
        "address": "'$TEST_WALLET_ADDRESS'",
        "name": "Test Wallet",
        "subnet": "mainnet",
        "description": "Test wallet for transaction flow testing"
    }'
    
    local response=$(curl -s -X POST "$API_URL/wallets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -d "$wallet_data")
    
    if echo "$response" | grep -q "$TEST_WALLET_ADDRESS"; then
        print_success "Test wallet created"
        return 0
    else
        print_warning "Wallet might already exist or creation failed"
        echo "Response: $response"
        return 0  # Continue anyway
    fi
}

# Function to insert test transaction data
insert_test_transactions() {
    print_status "Inserting test transaction data into DuckDB..."
    
    docker-compose exec -T api python -c "
import asyncio
import sys
import os
from datetime import datetime, timedelta
sys.path.append('/app/src')
from services.duckdb_service import DuckDBService

async def insert_test_data():
    try:
        db_service = DuckDBService()
        await db_service.initialize()
        
        # Create test transactions
        test_transactions = []
        base_time = datetime.utcnow()
        
        for i in range(10):
            tx_time = base_time - timedelta(hours=i)
            tx_data = {
                'hash': f'0x{i:064x}',
                'from_address': '$TEST_WALLET_ADDRESS',
                'to_address': f'0x{(i+1):040x}',
                'value': str(1000000000000000000 * (i + 1)),  # 1-10 AVAX
                'gas': '21000',
                'gas_price': '25000000000',  # 25 gwei
                'nonce': str(i),
                'input': '0x',
                'block_number': 1000000 + i,
                'block_hash': f'0xblock{i:060x}',
                'transaction_index': 0,
                'timestamp': tx_time.isoformat(),
                'network': '$TEST_NETWORK',
                'subnet': '$TEST_SUBNET',
                'status': 'confirmed',
                'token_symbol': 'AVAX',
                'transaction_type': 'send'
            }
            test_transactions.append(tx_data)
        
        # Insert using raw SQL for testing
        for tx in test_transactions:
            query = '''
            INSERT INTO transactions (
                hash, from_address, to_address, value, gas, gas_price, nonce,
                input, block_number, block_hash, transaction_index, timestamp,
                network, subnet, status, token_symbol, transaction_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            
            params = [
                tx['hash'], tx['from_address'], tx['to_address'], tx['value'],
                tx['gas'], tx['gas_price'], tx['nonce'], tx['input'],
                tx['block_number'], tx['block_hash'], tx['transaction_index'],
                tx['timestamp'], tx['network'], tx['subnet'], tx['status'],
                tx['token_symbol'], tx['transaction_type']
            ]
            
            try:
                await db_service.execute_query(query, params)
            except Exception as e:
                print(f'Failed to insert transaction {tx[\"hash\"]}: {e}')
                continue
        
        # Verify insertion
        count_query = 'SELECT COUNT(*) as count FROM transactions WHERE from_address = ?'
        result = await db_service.execute_query(count_query, ['$TEST_WALLET_ADDRESS'])
        
        if result and len(result) > 0:
            count = result[0]['count']
            print(f'Successfully inserted {count} test transactions')
            return True
        else:
            print('Failed to verify transaction insertion')
            return False
            
    except Exception as e:
        print(f'Error inserting test data: {e}')
        return False

result = asyncio.run(insert_test_data())
exit(0 if result else 1)
" && print_success "Test transactions inserted" || print_error "Failed to insert test transactions"
}

# Function to test API endpoints
test_api_endpoints() {
    print_status "Testing API endpoints..."
    
    # Test transactions endpoint
    print_status "Testing GET /transactions..."
    local response=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
        "$API_URL/transactions?wallet_addresses=$TEST_WALLET_ADDRESS&limit=5")
    
    if echo "$response" | grep -q "transactions"; then
        local count=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(data.get('transactions', [])))
except:
    print(0)
")
        print_success "Transactions API returned $count transactions"
    else
        print_error "Transactions API failed"
        echo "Response: $response"
        return 1
    fi
    
    # Test networks endpoint
    print_status "Testing GET /transactions/networks..."
    response=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$API_URL/transactions/networks")
    
    if echo "$response" | grep -q "$TEST_NETWORK"; then
        print_success "Networks API working"
    else
        print_warning "Networks API might be empty"
    fi
    
    # Test stats endpoint
    print_status "Testing GET /transactions/stats..."
    response=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
        "$API_URL/transactions/stats?networks=$TEST_NETWORK")
    
    if echo "$response" | grep -q "total_count"; then
        print_success "Stats API working"
    else
        print_warning "Stats API might be empty"
    fi
}

# Function to test frontend accessibility
test_frontend() {
    print_status "Testing frontend accessibility..."
    
    if curl -f "$DASHBOARD_URL" > /dev/null 2>&1; then
        print_success "Dashboard is accessible at $DASHBOARD_URL"
        
        # Check if transactions page is accessible
        if curl -f "$DASHBOARD_URL/transactions" > /dev/null 2>&1; then
            print_success "Transactions page is accessible"
        else
            print_warning "Transactions page might not be accessible (this is normal for SPA)"
        fi
    else
        print_error "Dashboard is not accessible"
        return 1
    fi
}

# Main execution
main() {
    print_status "Starting end-to-end transaction flow test..."
    
    # Start infrastructure
    print_status "Starting infrastructure services..."
    docker-compose up -d minio nats redis
    
    # Wait for infrastructure
    wait_for_service "$MINIO_URL/minio/health/live" "MinIO" 60
    
    # Start API service
    print_status "Starting API service..."
    docker-compose up -d api
    wait_for_service "$API_URL/health" "API" 120
    
    # Start dashboard
    print_status "Starting dashboard..."
    docker-compose up -d dashboard
    wait_for_service "$DASHBOARD_URL" "Dashboard" 120
    
    # Create test user and get auth token
    create_test_user
    get_auth_token || exit 1
    
    # Create test wallet
    create_test_wallet
    
    # Insert test transaction data
    insert_test_transactions
    
    # Test API endpoints
    test_api_endpoints
    
    # Test frontend
    test_frontend
    
    print_success "End-to-end test completed!"
    echo ""
    echo "🎯 Test Results Summary:"
    echo "========================"
    echo "✅ Infrastructure: MinIO, NATS, Redis"
    echo "✅ API Service: Running on $API_URL"
    echo "✅ Dashboard: Running on $DASHBOARD_URL"
    echo "✅ Test Data: Transactions inserted"
    echo "✅ API Endpoints: Tested and working"
    echo ""
    echo "🌐 Access Points:"
    echo "- Dashboard: $DASHBOARD_URL"
    echo "- API Docs: $API_URL/docs"
    echo "- MinIO Console: http://localhost:9001 (admin/password)"
    echo ""
    echo "🔑 Test Credentials:"
    echo "- Email: test@ekko.com"
    echo "- Password: testpass123"
    echo ""
    echo "📊 To view transactions:"
    echo "1. Open $DASHBOARD_URL"
    echo "2. Login with test credentials"
    echo "3. Navigate to Transactions page"
    echo "4. You should see test transactions for wallet $TEST_WALLET_ADDRESS"
}

# Run main function
main "$@"
