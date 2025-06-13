#!/usr/bin/env python3

"""
Test DuckDB connection and MinIO access.
"""

import sys
import os
import asyncio

# Add src path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

async def test_duckdb():
    """Test DuckDB service connection."""
    try:
        print("🧪 Testing DuckDB service...")
        
        # Test basic import
        try:
            import duckdb
            print("✅ DuckDB package available")

            # Try to import the service
            from src.services.duckdb_service import DuckDBService
            print("✅ DuckDB service import successful")
        except ImportError as e:
            print(f"❌ DuckDB service import failed: {e}")
            print("Checking if duckdb package is installed...")
            try:
                import duckdb
                print("✅ DuckDB package is installed")
            except ImportError:
                print("❌ DuckDB package not installed")
            return False
        
        # Test service initialization
        try:
            service = DuckDBService()
            await service.initialize()
            print("✅ DuckDB service initialized")
        except Exception as e:
            print(f"❌ DuckDB service initialization failed: {e}")
            return False
        
        # Test basic connection
        try:
            result = await service.test_connection()
            print(f"✅ DuckDB connection test: {result}")
        except Exception as e:
            print(f"❌ DuckDB connection test failed: {e}")
            return False
        
        # Test table info
        try:
            info = await service.get_table_info()
            print(f"✅ DuckDB table info: {info}")
        except Exception as e:
            print(f"❌ DuckDB table info failed: {e}")
            print("This is expected if no transaction data exists yet")
        
        # Test simple query
        try:
            result = await service.execute_query("SELECT 1 as test")
            print(f"✅ DuckDB simple query result: {result}")
        except Exception as e:
            print(f"❌ DuckDB simple query failed: {e}")
            return False
        
        await service.close()
        print("✅ DuckDB service test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ DuckDB service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_duckdb())
    sys.exit(0 if result else 1)
