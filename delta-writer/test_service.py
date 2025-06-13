#!/usr/bin/env python3
"""
Test script for the Delta Writer service.
Sends test events to NATS and verifies they're written to Delta Lake.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
import nats
from nats.js import JetStreamContext

async def create_test_event(network="Avalanche", subnet="Mainnet", tx_hash=None):
    """Create a test blockchain event."""
    if tx_hash is None:
        tx_hash = f"0x{int(time.time()):x}{'0' * 50}"[:66]
    
    return {
        "event_type": "wallet_tx",
        "entity": {
            "type": "wallet",
            "chain": "avax",
            "address": "0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF"
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tx_hash": tx_hash,
        "details": {
            "from": "0x742d35Cc6634C0532925a3b8D4C9db96590e4CAF",
            "to": "0x8ba1f109551bD432803012645Hac136c22C501e",
            "value": "1000000000000000000",
            "token": "AVAX",
            "direction": "out",
            "tx_type": "send",
            "gas": "21000",
            "gas_price": "25000000000",
            "nonce": "1",
            "input": "0x",
            "status": "confirmed"
        },
        "metadata": {
            "network": network,
            "subnet": subnet,
            "vm_type": "EVM",
            "block_number": 12345678,
            "block_hash": f"0x{int(time.time()):x}{'0' * 50}"[:66],
            "tx_index": 0,
            "year": datetime.now().year,
            "month": datetime.now().month,
            "day": datetime.now().day,
            "hour": datetime.now().hour
        }
    }

async def test_nats_connection():
    """Test NATS connection and JetStream setup."""
    print("🔌 Testing NATS connection...")
    
    try:
        # Connect to NATS
        nc = await nats.connect("nats://localhost:4222")
        js = nc.jetstream()
        
        print("✅ Connected to NATS")
        
        # Use existing transactions-test stream for testing
        try:
            stream_info = await js.stream_info("transactions-test")
            print(f"✅ Stream 'transactions-test' exists: {stream_info.config.name}")
        except:
            print("🆕 Creating transactions-test stream...")
            await js.add_stream(
                name="transactions-test",
                subjects=["transactions.test.>"],
                retention="limits",
                max_msgs=100000,
                max_bytes=100000000,
                storage="file"
            )
            print("✅ Created transactions-test stream")
        
        await nc.close()
        return True
        
    except Exception as e:
        print(f"❌ NATS connection failed: {e}")
        return False

async def send_test_events(num_events=5):
    """Send test events to NATS using production subject patterns."""
    print(f"📤 Sending {num_events} test events with production subjects...")

    # Test subject patterns (using transactions.test.* for existing stream)
    subjects = [
        "transactions.test.subnet-evm.avalanche.mainnet",
        "transactions.test.subnet-evm.avalanche.fuji",
        "transactions.test.evm.ethereum.mainnet",
        "transactions.test.evm.polygon.mainnet",
        "transactions.test.subnet-evm.avalanche.mainnet"  # Repeat for more Avalanche events
    ]

    try:
        # Connect to NATS
        nc = await nats.connect("nats://localhost:4222")
        js = nc.jetstream()

        events_sent = 0

        for i in range(num_events):
            # Pick a subject for this event
            subject = subjects[i % len(subjects)]

            # Parse network/subnet from subject
            # Format: transactions.test.{vmtype}.{network}.{subnet}
            parts = subject.split('.')
            network = parts[3] if len(parts) > 3 else "unknown"
            subnet = parts[4] if len(parts) > 4 else "mainnet"

            # Create test event
            event = await create_test_event(
                network=network.title(),
                subnet=subnet.title(),
                tx_hash=f"0xtest{i:010d}{'0' * 50}"[:66]
            )

            # Send to NATS with production subject pattern
            await js.publish(subject, json.dumps(event).encode())

            events_sent += 1
            print(f"📨 Sent event {i+1}/{num_events} to {subject}")

            # Small delay between events
            await asyncio.sleep(0.1)

        await nc.close()
        print(f"✅ Successfully sent {events_sent} events")
        return True

    except Exception as e:
        print(f"❌ Failed to send events: {e}")
        return False

async def check_delta_tables():
    """Check if Delta tables were created (requires DuckDB)."""
    print("🔍 Checking for Delta tables...")
    
    try:
        import duckdb
        
        # Connect to DuckDB
        conn = duckdb.connect()
        
        # Install extensions
        conn.execute("INSTALL delta;")
        conn.execute("LOAD delta;")
        conn.execute("INSTALL aws;")
        conn.execute("LOAD aws;")
        
        # Configure S3 settings
        conn.execute("""
            SET s3_region='us-east-1';
            SET s3_endpoint='http://localhost:9000/';
            SET s3_access_key_id='minioadmin';
            SET s3_secret_access_key='minioadmin';
            SET s3_use_ssl=false;
        """)
        
        # Try to read from Delta table
        table_path = "s3://blockchain-events/test-events/avalanche/mainnet"
        
        try:
            result = conn.execute(f"SELECT COUNT(*) FROM delta_scan('{table_path}')").fetchone()
            count = result[0] if result else 0
            print(f"✅ Found {count} events in Delta table: {table_path}")
            
            if count > 0:
                # Show sample data
                sample = conn.execute(f"SELECT event_type, tx_hash, timestamp FROM delta_scan('{table_path}') LIMIT 3").fetchall()
                print("📊 Sample events:")
                for row in sample:
                    print(f"   - {row[0]}: {row[1]} at {row[2]}")
            
            return True
            
        except Exception as e:
            print(f"⚠️  Delta table not found or empty: {e}")
            return False
        
    except ImportError:
        print("⚠️  DuckDB not available for Delta table checking")
        return False
    except Exception as e:
        print(f"❌ Error checking Delta tables: {e}")
        return False

async def main():
    """Main test function."""
    print("🧪 Starting Delta Writer Service Tests")
    print("=" * 50)
    
    # Test 1: NATS Connection
    if not await test_nats_connection():
        print("❌ NATS test failed - stopping")
        return
    
    print()
    
    # Test 2: Send test events
    if not await send_test_events(5):
        print("❌ Event sending failed - stopping")
        return
    
    print()
    print("⏳ Waiting 10 seconds for events to be processed...")
    await asyncio.sleep(10)
    
    # Test 3: Check Delta tables
    await check_delta_tables()
    
    print()
    print("🎉 Tests completed!")
    print("💡 Next steps:")
    print("   1. Check Delta Writer service logs")
    print("   2. Check MinIO console: http://localhost:9001")
    print("   3. Check metrics: http://localhost:9091/metrics")

if __name__ == "__main__":
    asyncio.run(main())
