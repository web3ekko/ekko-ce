"""
Delta Lake service for querying blockchain event data.
"""

import duckdb
import asyncio
import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import os
from ..config import settings

logger = logging.getLogger(__name__)

class DeltaService:
    """
    Service for executing DuckDB queries against Delta Lake tables stored in MinIO.
    """
    
    def __init__(self):
        self.connection_pool = []
        self.pool_size = 5
        self._initialized = False
    
    async def initialize(self):
        """Initialize the Delta service and connection pool."""
        if self._initialized:
            return
            
        try:
            # Create connection pool
            for _ in range(self.pool_size):
                conn = await self._create_connection()
                self.connection_pool.append(conn)
            
            self._initialized = True
            logger.info(f"Delta service initialized with {self.pool_size} connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize Delta service: {str(e)}")
            raise
    
    async def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a new DuckDB connection with Delta Lake configuration."""
        try:
            # Create connection
            conn = duckdb.connect()
            
            # Install and load required extensions
            conn.execute("INSTALL delta;")
            conn.execute("LOAD delta;")
            conn.execute("INSTALL aws;")
            conn.execute("LOAD aws;")
            
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
            
            # Create view for events table pointing to Delta Lake
            # This creates a union view across all network/subnet Delta tables
            delta_base_path = getattr(settings, 'DELTA_TABLE_BASE_PATH', 'events')
            bucket = getattr(settings, 'MINIO_BUCKET', 'blockchain-events')

            # For now, create a view that can read from specific network/subnet tables
            # In production, you might want to discover tables dynamically
            conn.execute(f"""
                CREATE OR REPLACE VIEW events AS
                SELECT * FROM delta_scan('s3://{bucket}/{delta_base_path}/avalanche/mainnet')
                UNION ALL
                SELECT * FROM delta_scan('s3://{bucket}/{delta_base_path}/ethereum/mainnet')
                UNION ALL
                SELECT * FROM delta_scan('s3://{bucket}/{delta_base_path}/polygon/mainnet')
            """)
            
            logger.info("DuckDB connection created and configured with Delta Lake")
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
        """Test the Delta Lake connection and MinIO access."""
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
                
                # Test Delta Lake access by trying to read from events view
                def _test_delta():
                    try:
                        result = conn.execute("SELECT COUNT(*) FROM events LIMIT 1").fetchone()
                        return True
                    except Exception:
                        return False
                
                delta_test = await loop.run_in_executor(None, _test_delta)
                
                logger.info(f"Delta connection test: basic={basic_test}, delta={delta_test}")
                return basic_test and delta_test
                
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    async def get_table_info(self) -> Dict[str, Any]:
        """Get information about the events table."""
        try:
            queries = {
                'schema': "DESCRIBE events",
                'count': "SELECT COUNT(*) as total_events FROM events",
                'date_range': """
                    SELECT 
                        MIN(timestamp) as earliest_event,
                        MAX(timestamp) as latest_event
                    FROM events
                """,
                'event_types': """
                    SELECT 
                        event_type,
                        COUNT(*) as count
                    FROM events 
                    GROUP BY event_type
                    ORDER BY count DESC
                """,
                'chains': """
                    SELECT 
                        chain,
                        COUNT(*) as count
                    FROM events 
                    GROUP BY chain
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
    
    async def get_delta_table_for_network(
        self,
        network: str,
        subnet: str = "mainnet"
    ) -> str:
        """Get the Delta table path for a specific network/subnet."""
        delta_base_path = getattr(settings, 'DELTA_TABLE_BASE_PATH', 'events')
        bucket = getattr(settings, 'MINIO_BUCKET', 'blockchain-events')
        return f"s3://{bucket}/{delta_base_path}/{network.lower()}/{subnet.lower()}"

    async def get_events_for_wallet(
        self,
        wallet_address: str,
        chain: str = None,
        event_types: List[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get events for a specific wallet address."""
        
        where_conditions = ["entity_address = ?"]
        params = [wallet_address.lower()]
        
        if chain:
            where_conditions.append("chain = ?")
            params.append(chain.lower())
        
        if event_types:
            placeholders = ','.join(['?' for _ in event_types])
            where_conditions.append(f"event_type IN ({placeholders})")
            params.extend(event_types)
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
            SELECT 
                event_type,
                tx_hash,
                timestamp,
                entity_type,
                chain,
                entity_address,
                entity_name,
                entity_symbol,
                network,
                subnet,
                vm_type,
                block_number,
                block_hash,
                tx_index,
                details
            FROM events
            WHERE {where_clause}
            ORDER BY timestamp DESC, block_number DESC, tx_index DESC
            LIMIT ? OFFSET ?
        """
        
        params.extend([limit, offset])
        return await self.execute_query(query, params)
    
    async def get_token_transfers(
        self,
        token_address: str = None,
        token_symbol: str = None,
        from_address: str = None,
        to_address: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get token transfer events with filtering."""
        
        where_conditions = ["event_type = 'token_transfer'"]
        params = []
        
        if token_address:
            where_conditions.append("JSON_EXTRACT(details, '$.token_address') = ?")
            params.append(token_address.lower())
        
        if token_symbol:
            where_conditions.append("JSON_EXTRACT(details, '$.token_symbol') = ?")
            params.append(token_symbol.upper())
        
        if from_address:
            where_conditions.append("JSON_EXTRACT(details, '$.from') = ?")
            params.append(from_address.lower())
        
        if to_address:
            where_conditions.append("JSON_EXTRACT(details, '$.to') = ?")
            params.append(to_address.lower())
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
            SELECT 
                tx_hash,
                timestamp,
                chain,
                network,
                block_number,
                details
            FROM events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        
        params.extend([limit, offset])
        return await self.execute_query(query, params)
    
    async def close(self):
        """Close all connections in the pool."""
        for conn in self.connection_pool:
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {str(e)}")
        
        self.connection_pool.clear()
        self._initialized = False
        logger.info("Delta service closed")

# Global instance
delta_service = DeltaService()

async def get_delta_service() -> DeltaService:
    """Dependency injection for Delta service."""
    if not delta_service._initialized:
        await delta_service.initialize()
    return delta_service
