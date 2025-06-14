"""
DuckDB service for querying blockchain transaction data from MinIO Arrow files.
"""

import duckdb
import asyncio
import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import os
from ..config import settings

logger = logging.getLogger(__name__)

class DuckDBService:
    """
    Service for executing DuckDB queries against Arrow files stored in MinIO.
    """
    
    def __init__(self):
        self.connection_pool = []
        self.pool_size = 5
        self._initialized = False
    
    async def initialize(self):
        """Initialize the DuckDB service and connection pool."""
        if self._initialized:
            return
            
        try:
            # Create connection pool
            for _ in range(self.pool_size):
                conn = await self._create_connection()
                self.connection_pool.append(conn)
            
            self._initialized = True
            logger.info(f"DuckDB service initialized with {self.pool_size} connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize DuckDB service: {str(e)}")
            raise
    
    async def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a new DuckDB connection with MinIO configuration."""
        try:
            # Create connection
            conn = duckdb.connect()
            
            # Install and load required extensions
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")
            
            # Configure MinIO/S3 settings
            # Format endpoint as full URL with trailing slash
            endpoint = settings.MINIO_ENDPOINT
            if not endpoint.startswith(('http://', 'https://')):
                protocol = 'https' if settings.MINIO_SECURE else 'http'
                endpoint = f"{protocol}://{endpoint}"

            # Ensure endpoint ends with /
            if not endpoint.endswith('/'):
                endpoint += '/'

            logger.info(f"Configuring DuckDB with MinIO endpoint: {endpoint}")

            conn.execute(f"""
                SET s3_region='{settings.MINIO_REGION}';
                SET s3_endpoint='{endpoint}';
                SET s3_access_key_id='{settings.MINIO_ACCESS_KEY}';
                SET s3_secret_access_key='{settings.MINIO_SECRET_KEY}';
                SET s3_use_ssl={'true' if settings.MINIO_SECURE else 'false'};
            """)
            
            # Create a simple test transactions table for development
            # This will be replaced with actual Delta Lake integration later
            conn.execute("""
                CREATE OR REPLACE TABLE transactions (
                    hash VARCHAR PRIMARY KEY,
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
                    decoded_call VARCHAR,
                    token_symbol VARCHAR,
                    transaction_type VARCHAR
                )
            """)

            # Insert some test data to verify the connection works
            conn.execute("""
                INSERT OR REPLACE INTO transactions VALUES
                ('0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
                 '0x1111111111111111111111111111111111111111',
                 '0x2222222222222222222222222222222222222222',
                 '1000000000000000000', '21000', '20000000000', '1', '0x',
                 12345678, '0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
                 0, '2024-01-15 10:30:00', 'avalanche', 'mainnet', 'confirmed',
                 NULL, 'AVAX', 'send'),
                ('0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
                 '0x3333333333333333333333333333333333333333',
                 '0x4444444444444444444444444444444444444444',
                 '500000000000000000', '21000', '25000000000', '2', '0x',
                 12345679, '0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
                 1, '2024-01-15 11:45:00', 'ethereum', 'mainnet', 'confirmed',
                 NULL, 'ETH', 'send')
            """)

            logger.info("DuckDB connection created with test transactions table")
            
            logger.info("DuckDB connection created and configured")
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create DuckDB connection: {str(e)}")
            raise
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        if not self._initialized:
            await self.initialize()
        
        if not self.connection_pool:
            # Create new connection if pool is empty
            conn = await self._create_connection()
        else:
            conn = self.connection_pool.pop()
        
        try:
            yield conn
        finally:
            # Return connection to pool
            if len(self.connection_pool) < self.pool_size:
                self.connection_pool.append(conn)
            else:
                conn.close()
    
    async def execute_query(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a DuckDB query and return results as a list of dictionaries.
        
        Args:
            query: SQL query string
            params: Optional list of parameters for the query
            
        Returns:
            List of dictionaries representing query results
        """
        try:
            async with self.get_connection() as conn:
                # Execute query in a thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                
                def _execute():
                    if params:
                        result = conn.execute(query, params).fetchall()
                        columns = [desc[0] for desc in conn.description]
                    else:
                        result = conn.execute(query).fetchall()
                        columns = [desc[0] for desc in conn.description]
                    
                    # Convert to list of dictionaries
                    return [dict(zip(columns, row)) for row in result]
                
                result = await loop.run_in_executor(None, _execute)
                
                logger.debug(f"Query executed successfully, returned {len(result)} rows")
                return result
                
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise
    
    async def test_connection(self) -> bool:
        """Test the DuckDB connection and MinIO access."""
        try:
            async with self.get_connection() as conn:
                # Test basic query
                loop = asyncio.get_event_loop()
                
                def _test():
                    result = conn.execute("SELECT 1 as test").fetchone()
                    return result[0] == 1
                
                basic_test = await loop.run_in_executor(None, _test)
                
                if not basic_test:
                    return False
                
                # Test MinIO access by trying to read from transactions view
                def _test_minio():
                    try:
                        result = conn.execute("SELECT COUNT(*) FROM transactions LIMIT 1").fetchone()
                        return True
                    except Exception:
                        return False
                
                minio_test = await loop.run_in_executor(None, _test_minio)
                
                logger.info(f"DuckDB connection test: basic={basic_test}, minio={minio_test}")
                return basic_test and minio_test
                
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    async def get_table_info(self) -> Dict[str, Any]:
        """Get information about the transactions table."""
        try:
            queries = {
                'schema': "DESCRIBE transactions",
                'count': "SELECT COUNT(*) as total_transactions FROM transactions",
                'date_range': """
                    SELECT 
                        MIN(timestamp) as earliest_transaction,
                        MAX(timestamp) as latest_transaction
                    FROM transactions
                """,
                'networks': """
                    SELECT 
                        network,
                        COUNT(*) as count
                    FROM transactions 
                    GROUP BY network
                    ORDER BY count DESC
                """
            }
            
            results = {}
            for key, query in queries.items():
                try:
                    results[key] = await self.execute_query(query)
                except Exception as e:
                    logger.warning(f"Failed to execute {key} query: {str(e)}")
                    results[key] = []
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting table info: {str(e)}")
            raise
    
    async def close(self):
        """Close all connections in the pool."""
        for conn in self.connection_pool:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {str(e)}")
        
        self.connection_pool.clear()
        self._initialized = False
        logger.info("DuckDB service closed")

# Global instance
duckdb_service = DuckDBService()

async def get_duckdb_service() -> DuckDBService:
    """Dependency injection for DuckDB service."""
    if not duckdb_service._initialized:
        await duckdb_service.initialize()
    return duckdb_service
