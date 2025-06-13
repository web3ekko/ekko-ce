#!/usr/bin/env python3

"""
Insert test transaction data into DuckDB for frontend testing.
This script creates sample transactions that can be viewed on the dashboard.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import random

# Add the API source path
sys.path.append('/app/src')

async def insert_test_transactions():
    """Insert test transaction data into DuckDB."""
    try:
        # Import DuckDB service
        from services.duckdb_service import DuckDBService
        
        print("🧪 Inserting test transaction data...")
        
        # Initialize DuckDB service
        db_service = DuckDBService()
        await db_service.initialize()
        
        # Test wallet addresses
        test_wallets = [
            "0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF",
            "0x8ba1f109551bD432803012645Hac136c22C501e",
            "0x1234567890123456789012345678901234567890",
            "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        ]
        
        # Create test transactions
        test_transactions = []
        base_time = datetime.utcnow()
        
        print(f"📝 Creating test transactions...")
        
        for i in range(50):  # Create 50 test transactions
            tx_time = base_time - timedelta(hours=i, minutes=random.randint(0, 59))
            from_wallet = random.choice(test_wallets)
            to_wallet = random.choice([w for w in test_wallets if w != from_wallet])
            
            # Random transaction values (1-100 AVAX)
            value_avax = random.uniform(0.1, 100.0)
            value_wei = int(value_avax * 1e18)
            
            tx_data = {
                'hash': f'0x{i:064x}',
                'from_address': from_wallet,
                'to_address': to_wallet,
                'value': str(value_wei),
                'gas': str(random.randint(21000, 100000)),
                'gas_price': str(random.randint(20000000000, 50000000000)),  # 20-50 gwei
                'nonce': str(random.randint(0, 1000)),
                'input': '0x' if random.random() > 0.3 else f'0x{random.randint(1000000, 9999999):x}',
                'block_number': 1000000 + i,
                'block_hash': f'0xblock{i:060x}',
                'transaction_index': random.randint(0, 10),
                'timestamp': tx_time.isoformat(),
                'network': random.choice(['Avalanche', 'Ethereum', 'Polygon']),
                'subnet': random.choice(['Mainnet', 'Testnet']),
                'status': random.choice(['confirmed', 'confirmed', 'confirmed', 'failed']),  # Mostly confirmed
                'token_symbol': random.choice(['AVAX', 'ETH', 'MATIC']),
                'transaction_type': random.choice(['send', 'receive', 'contract_interaction'])
            }
            test_transactions.append(tx_data)
        
        print(f"💾 Inserting {len(test_transactions)} transactions into DuckDB...")
        
        # Insert transactions one by one for better error handling
        success_count = 0
        for i, tx in enumerate(test_transactions):
            try:
                # Create a simple insert query
                query = '''
                CREATE TABLE IF NOT EXISTS transactions (
                    hash VARCHAR,
                    from_address VARCHAR,
                    to_address VARCHAR,
                    value VARCHAR,
                    gas VARCHAR,
                    gas_price VARCHAR,
                    nonce VARCHAR,
                    input VARCHAR,
                    block_number BIGINT,
                    block_hash VARCHAR,
                    transaction_index INTEGER,
                    timestamp TIMESTAMP,
                    network VARCHAR,
                    subnet VARCHAR,
                    status VARCHAR,
                    token_symbol VARCHAR,
                    transaction_type VARCHAR
                )
                '''
                await db_service.execute_query(query)
                
                # Insert the transaction
                insert_query = '''
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
                
                await db_service.execute_query(insert_query, params)
                success_count += 1
                
                if (i + 1) % 10 == 0:
                    print(f"   ✅ Inserted {i + 1}/{len(test_transactions)} transactions")
                    
            except Exception as e:
                print(f"   ❌ Failed to insert transaction {tx['hash']}: {e}")
                continue
        
        print(f"✅ Successfully inserted {success_count}/{len(test_transactions)} transactions")
        
        # Verify insertion
        count_query = 'SELECT COUNT(*) as count FROM transactions'
        result = await db_service.execute_query(count_query)
        
        if result and len(result) > 0:
            total_count = result[0]['count']
            print(f"📊 Total transactions in database: {total_count}")
        
        # Show sample data
        sample_query = '''
        SELECT hash, from_address, to_address, value, network, status, timestamp 
        FROM transactions 
        ORDER BY timestamp DESC 
        LIMIT 5
        '''
        sample_result = await db_service.execute_query(sample_query)
        
        if sample_result:
            print(f"\n📋 Sample transactions:")
            for tx in sample_result:
                print(f"   🔗 {tx['hash'][:10]}... | {tx['network']} | {tx['status']} | {tx['timestamp']}")
        
        print(f"\n🎉 Test data insertion completed!")
        print(f"🌐 You can now view transactions at: http://localhost:3000")
        
        return True
        
    except Exception as e:
        print(f"❌ Error inserting test data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(insert_test_transactions())
    sys.exit(0 if result else 1)
