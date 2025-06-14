#!/usr/bin/env python3
"""
Benchmark DuckDB performance when reading transaction data from MinIO.
"""

import duckdb
import time
import statistics
from datetime import datetime
import json

def setup_duckdb_connection():
    """Setup DuckDB connection with S3 configuration for MinIO."""
    conn = duckdb.connect(':memory:')
    
    # Install and load httpfs extension for S3 support
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")
    
    # Configure S3 settings for MinIO
    conn.execute("""
        SET s3_region='us-east-1';
        SET s3_url_style='path';
        SET s3_endpoint='minio:9000';
        SET s3_access_key_id='minioadmin';
        SET s3_secret_access_key='minioadmin';
        SET s3_use_ssl=false;
    """)
    
    return conn

def time_query(conn, query, description, iterations=1):
    """Time a query execution and return statistics."""
    print(f"\n🔍 {description}")
    print(f"Query: {query}")
    
    times = []
    results = None
    
    for i in range(iterations):
        start_time = time.perf_counter()
        try:
            result = conn.execute(query).fetchall()
            end_time = time.perf_counter()
            
            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
            times.append(execution_time)
            
            if i == 0:  # Store first result for verification
                results = result
                
            print(f"  Run {i+1}: {execution_time:.2f}ms")
            
        except Exception as e:
            print(f"  ❌ Error in run {i+1}: {e}")
            return None, None
    
    if times:
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"  📊 Results: {len(results)} rows")
        print(f"  ⏱️  Average: {avg_time:.2f}ms")
        print(f"  ⚡ Fastest: {min_time:.2f}ms")
        print(f"  🐌 Slowest: {max_time:.2f}ms")
        
        if iterations > 1:
            median_time = statistics.median(times)
            print(f"  📈 Median: {median_time:.2f}ms")
            if len(times) > 1:
                stdev = statistics.stdev(times)
                print(f"  📏 Std Dev: {stdev:.2f}ms")
    
    return times, results

def benchmark_basic_queries(conn):
    """Benchmark basic query patterns."""
    print("\n" + "="*60)
    print("🚀 BASIC QUERY BENCHMARKS")
    print("="*60)
    
    # Test 1: Count all transactions
    time_query(
        conn,
        "SELECT COUNT(*) FROM 's3://blockchain-events/transactions/avalanche/mainnet/transactions.parquet'",
        "Count all Avalanche mainnet transactions",
        3
    )
    
    # Test 2: Select all columns (full scan)
    time_query(
        conn,
        "SELECT * FROM 's3://blockchain-events/transactions/avalanche/mainnet/transactions.parquet' LIMIT 10",
        "Select first 10 transactions (full columns)",
        3
    )
    
    # Test 3: Select specific columns
    time_query(
        conn,
        """SELECT hash, from_address, to_address, value, timestamp 
           FROM 's3://blockchain-events/transactions/avalanche/mainnet/transactions.parquet' 
           LIMIT 20""",
        "Select specific columns (projection)",
        3
    )
    
    # Test 4: Filter by network
    time_query(
        conn,
        """SELECT COUNT(*) 
           FROM 's3://blockchain-events/transactions/avalanche/mainnet/transactions.parquet' 
           WHERE network = 'avalanche'""",
        "Filter by network (WHERE clause)",
        3
    )

def benchmark_aggregation_queries(conn):
    """Benchmark aggregation queries."""
    print("\n" + "="*60)
    print("📊 AGGREGATION BENCHMARKS")
    print("="*60)
    
    # Test 1: Group by token symbol
    time_query(
        conn,
        """SELECT token_symbol, COUNT(*) as tx_count, AVG(CAST(value AS BIGINT)) as avg_value
           FROM 's3://blockchain-events/transactions/avalanche/mainnet/transactions.parquet'
           GROUP BY token_symbol
           ORDER BY tx_count DESC""",
        "Group by token symbol with aggregations",
        3
    )
    
    # Test 2: Time-based aggregation
    time_query(
        conn,
        """SELECT DATE(timestamp) as date, COUNT(*) as daily_transactions
           FROM 's3://blockchain-events/transactions/avalanche/mainnet/transactions.parquet'
           GROUP BY DATE(timestamp)
           ORDER BY date DESC
           LIMIT 10""",
        "Daily transaction counts",
        3
    )
    
    # Test 3: Complex aggregation with multiple conditions
    time_query(
        conn,
        """SELECT 
               transaction_type,
               status,
               COUNT(*) as count,
               MIN(CAST(value AS BIGINT)) as min_value,
               MAX(CAST(value AS BIGINT)) as max_value
           FROM 's3://blockchain-events/transactions/avalanche/mainnet/transactions.parquet'
           WHERE status = 'confirmed'
           GROUP BY transaction_type, status
           ORDER BY count DESC""",
        "Multi-column grouping with filters",
        3
    )

def benchmark_multi_file_queries(conn):
    """Benchmark queries across multiple parquet files."""
    print("\n" + "="*60)
    print("🌐 MULTI-FILE BENCHMARKS")
    print("="*60)
    
    # Test 1: Union across all networks
    time_query(
        conn,
        """SELECT network, COUNT(*) as tx_count
           FROM (
               SELECT * FROM 's3://blockchain-events/transactions/avalanche/mainnet/transactions.parquet'
               UNION ALL
               SELECT * FROM 's3://blockchain-events/transactions/ethereum/mainnet/transactions.parquet'
               UNION ALL
               SELECT * FROM 's3://blockchain-events/transactions/polygon/mainnet/transactions.parquet'
           )
           GROUP BY network
           ORDER BY tx_count DESC""",
        "Cross-network transaction counts",
        3
    )
    
    # Test 2: Wildcard pattern matching
    time_query(
        conn,
        """SELECT network, subnet, COUNT(*) as tx_count
           FROM 's3://blockchain-events/transactions/*/*/transactions.parquet'
           GROUP BY network, subnet
           ORDER BY tx_count DESC""",
        "Wildcard pattern - all networks/subnets",
        3
    )

def benchmark_view_creation(conn):
    """Benchmark creating views and querying them."""
    print("\n" + "="*60)
    print("🔗 VIEW CREATION BENCHMARKS")
    print("="*60)
    
    # Create a view
    start_time = time.perf_counter()
    conn.execute("""
        CREATE OR REPLACE VIEW all_transactions AS
        SELECT * FROM 's3://blockchain-events/transactions/*/*/transactions.parquet'
    """)
    end_time = time.perf_counter()
    view_creation_time = (end_time - start_time) * 1000
    
    print(f"📋 View creation time: {view_creation_time:.2f}ms")
    
    # Query the view
    time_query(
        conn,
        "SELECT COUNT(*) FROM all_transactions",
        "Count from view (first time)",
        1
    )
    
    time_query(
        conn,
        "SELECT COUNT(*) FROM all_transactions",
        "Count from view (second time - cached)",
        3
    )
    
    # Complex query on view
    time_query(
        conn,
        """SELECT network, token_symbol, COUNT(*) as tx_count
           FROM all_transactions 
           WHERE status = 'confirmed'
           GROUP BY network, token_symbol
           ORDER BY tx_count DESC
           LIMIT 10""",
        "Complex query on view",
        3
    )

def main():
    """Run all benchmarks."""
    print("🎯 DuckDB MinIO Performance Benchmark")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Setup connection
    print("\n🔧 Setting up DuckDB connection...")
    conn = setup_duckdb_connection()
    
    # Verify connection works
    try:
        result = conn.execute("SELECT 1").fetchone()
        print("✅ DuckDB connection established")
    except Exception as e:
        print(f"❌ Failed to establish DuckDB connection: {e}")
        return
    
    # Run benchmarks
    try:
        benchmark_basic_queries(conn)
        benchmark_aggregation_queries(conn)
        benchmark_multi_file_queries(conn)
        benchmark_view_creation(conn)
        
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()
        print(f"\n🏁 Benchmark completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
