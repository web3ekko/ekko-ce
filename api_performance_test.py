#!/usr/bin/env python3
"""
Test the actual API performance when reading from MinIO vs fallback data.
"""

import time
import requests
import json
import statistics

def time_api_request(url, description, iterations=5):
    """Time API requests and return statistics."""
    print(f"\n🔍 {description}")
    print(f"URL: {url}")
    
    times = []
    response_data = None
    
    for i in range(iterations):
        start_time = time.perf_counter()
        try:
            response = requests.get(url)
            end_time = time.perf_counter()
            
            if response.status_code == 200:
                execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
                times.append(execution_time)
                
                if i == 0:  # Store first response for analysis
                    response_data = response.json()
                    
                print(f"  Run {i+1}: {execution_time:.2f}ms")
            else:
                print(f"  ❌ Error in run {i+1}: HTTP {response.status_code}")
                return None, None
                
        except Exception as e:
            print(f"  ❌ Error in run {i+1}: {e}")
            return None, None
    
    if times:
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        
        if response_data:
            total_transactions = response_data.get('total', 0)
            returned_transactions = len(response_data.get('transactions', []))
            print(f"  📊 Results: {returned_transactions} transactions returned, {total_transactions} total")
        
        print(f"  ⏱️  Average: {avg_time:.2f}ms")
        print(f"  ⚡ Fastest: {min_time:.2f}ms")
        print(f"  🐌 Slowest: {max_time:.2f}ms")
        
        if iterations > 1:
            median_time = statistics.median(times)
            print(f"  📈 Median: {median_time:.2f}ms")
            if len(times) > 1:
                stdev = statistics.stdev(times)
                print(f"  📏 Std Dev: {stdev:.2f}ms")
    
    return times, response_data

def test_api_performance():
    """Test API performance with different query patterns."""
    base_url = "http://localhost:8000/api"
    
    print("🎯 API Performance Test")
    print("="*60)
    
    # Test 1: Basic transaction list
    time_api_request(
        f"{base_url}/transactions/",
        "Basic transaction list (default limit)",
        5
    )
    
    # Test 2: Large limit
    time_api_request(
        f"{base_url}/transactions/?limit=100",
        "Large transaction list (limit=100)",
        5
    )
    
    # Test 3: With pagination
    time_api_request(
        f"{base_url}/transactions/?limit=20&offset=50",
        "Paginated transactions (offset=50)",
        5
    )
    
    # Test 4: Network filtering
    time_api_request(
        f"{base_url}/transactions/?network=avalanche",
        "Network filtered transactions",
        5
    )
    
    # Test 5: Multiple filters
    time_api_request(
        f"{base_url}/transactions/?network=avalanche&status=confirmed&limit=50",
        "Multiple filters (network + status)",
        5
    )

def main():
    """Run API performance tests."""
    print("🚀 Starting API Performance Tests...")
    print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        test_api_performance()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🏁 Tests completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
