"""
DuckLake service for querying transaction data stored in DuckLake format.
This service replaces the traditional DuckDB service for better versioning and change tracking.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import duckdb
from ..config import settings

logger = logging.getLogger(__name__)


class DuckLakeService:
    """
    Service for executing DuckDB queries against DuckLake-formatted transaction data.
    Provides versioning, change tracking, and time travel capabilities.
    """
    
    def __init__(self):
        self.connection_pool = []
        self.pool_size = 5
        self._initialized = False
        self.ducklake_catalog = "blockchain"
    
    async def initialize(self):
        """Initialize the DuckLake service and connection pool."""
        if self._initialized:
            return
            
        try:
            # Create connection pool
            for _ in range(self.pool_size):
                conn = await self._create_connection()
                self.connection_pool.append(conn)
            
            self._initialized = True
            logger.info(f"DuckLake service initialized with {self.pool_size} connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize DuckLake service: {str(e)}")
            raise
    
    async def _create_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a new DuckDB connection with DuckLake configuration."""
        try:
            # Create in-memory connection for DuckLake with SQLite catalog + MinIO storage
            conn = duckdb.connect()

            # Install and load required extensions
            conn.execute("INSTALL ducklake;")
            conn.execute("LOAD ducklake;")
            conn.execute("INSTALL sqlite;")  # For SQLite catalog support
            conn.execute("LOAD sqlite;")
            conn.execute("INSTALL aws;")     # Better S3/MinIO support
            conn.execute("LOAD aws;")

            # Create S3 secret for MinIO authentication
            conn.execute(f"""
                CREATE OR REPLACE SECRET minio_secret (
                    TYPE s3,
                    PROVIDER config,
                    KEY_ID '{settings.MINIO_ACCESS_KEY}',
                    SECRET '{settings.MINIO_SECRET_KEY}',
                    REGION '{settings.MINIO_REGION}',
                    ENDPOINT '{settings.MINIO_ENDPOINT}',
                    USE_SSL {'true' if settings.MINIO_SECURE else 'false'}
                );
            """)
            
            # Attach DuckLake database with SQLite catalog and MinIO storage
            if settings.DUCKLAKE_CATALOG_TYPE == "sqlite":
                attach_sql = f"""
                    ATTACH 'ducklake:sqlite:{settings.DUCKLAKE_CATALOG_PATH}' AS {self.ducklake_catalog}
                    (DATA_PATH '{settings.DUCKLAKE_DATA_PATH}');
                """
            elif settings.DUCKLAKE_CATALOG_TYPE == "duckdb":
                attach_sql = f"""
                    ATTACH 'ducklake:{settings.DUCKLAKE_CATALOG_PATH}' AS {self.ducklake_catalog}
                    (DATA_PATH '{settings.DUCKLAKE_DATA_PATH}');
                """
            else:
                raise ValueError(f"Unsupported catalog type: {settings.DUCKLAKE_CATALOG_TYPE}")

            conn.execute(attach_sql)
            
            # Verify connection by checking if transactions table exists
            result = conn.execute(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_catalog = '{self.ducklake_catalog}' 
                AND table_name = 'transactions'
            """).fetchall()
            
            if not result:
                logger.warning("Transactions table not found in DuckLake catalog")
            else:
                logger.info("DuckLake connection verified - transactions table found")
            
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create DuckLake connection: {str(e)}")
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
    
    async def execute_query(self, query: str, params: Optional[List] = None) -> List[Dict[str, Any]]:
        """
        Execute a query against the DuckLake database.
        
        Args:
            query: SQL query to execute
            params: Optional parameters for the query
            
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
            logger.error(f"Failed to execute query: {str(e)}")
            logger.error(f"Query: {query}")
            if params:
                logger.error(f"Params: {params}")
            raise
    
    async def get_transactions(
        self, 
        limit: int = 100, 
        offset: int = 0,
        network: Optional[str] = None,
        subnet: Optional[str] = None,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        snapshot_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get transactions with optional filtering and snapshot support.
        
        Args:
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            network: Filter by network (e.g., 'Avalanche')
            subnet: Filter by subnet (e.g., 'Mainnet')
            from_address: Filter by sender address
            to_address: Filter by recipient address
            start_time: Filter transactions after this time
            end_time: Filter transactions before this time
            snapshot_id: Query data as of a specific snapshot (time travel)
            
        Returns:
            List of transaction dictionaries
        """
        
        # Build WHERE clause
        where_conditions = []
        query_params = []
        
        if network:
            where_conditions.append("network = ?")
            query_params.append(network)
        
        if subnet:
            where_conditions.append("subnet = ?")
            query_params.append(subnet)
        
        if from_address:
            where_conditions.append("from_address = ?")
            query_params.append(from_address)
        
        if to_address:
            where_conditions.append("to_address = ?")
            query_params.append(to_address)
        
        if start_time:
            where_conditions.append("block_time >= ?")
            query_params.append(start_time)
        
        if end_time:
            where_conditions.append("block_time <= ?")
            query_params.append(end_time)
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Build query with optional snapshot support
        table_name = f"{self.ducklake_catalog}.transactions"
        if snapshot_id is not None:
            # Time travel query to specific snapshot
            table_name = f"(SELECT * FROM {table_name} WHERE snapshot_id <= {snapshot_id})"
        
        query = f"""
            SELECT 
                tx_hash as hash,
                from_address as from,
                to_address as to,
                value,
                gas_limit as gas,
                gas_price,
                nonce,
                input_data as input,
                block_number,
                block_hash,
                tx_index as transaction_index,
                block_time as timestamp,
                network,
                subnet,
                CASE WHEN success THEN 'confirmed' ELSE 'failed' END as status,
                ingested_at
            FROM {table_name}
            {where_clause}
            ORDER BY block_time DESC, tx_index ASC
            LIMIT ? OFFSET ?
        """
        
        query_params.extend([limit, offset])
        
        return await self.execute_query(query, query_params)
    
    async def get_transaction_count(
        self,
        network: Optional[str] = None,
        subnet: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        """Get total count of transactions matching the filters."""
        
        where_conditions = []
        query_params = []
        
        if network:
            where_conditions.append("network = ?")
            query_params.append(network)
        
        if subnet:
            where_conditions.append("subnet = ?")
            query_params.append(subnet)
        
        if start_time:
            where_conditions.append("block_time >= ?")
            query_params.append(start_time)
        
        if end_time:
            where_conditions.append("block_time <= ?")
            query_params.append(end_time)
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        query = f"""
            SELECT COUNT(*) as count
            FROM {self.ducklake_catalog}.transactions
            {where_clause}
        """
        
        result = await self.execute_query(query, query_params)
        return result[0]['count'] if result else 0
    
    async def get_snapshots(self) -> List[Dict[str, Any]]:
        """Get all snapshots in the DuckLake catalog."""
        query = f"SELECT * FROM ducklake_snapshots('{self.ducklake_catalog}') ORDER BY snapshot_id DESC"
        return await self.execute_query(query)
    
    async def get_table_info(self) -> List[Dict[str, Any]]:
        """Get information about tables in the DuckLake catalog."""
        query = f"SELECT * FROM ducklake_table_info('{self.ducklake_catalog}')"
        return await self.execute_query(query)
    
    async def get_recent_changes(
        self, 
        hours: int = 24,
        table_name: str = "transactions"
    ) -> List[Dict[str, Any]]:
        """Get recent changes to a table."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        query = f"""
            SELECT * FROM ducklake_table_changes(
                '{self.ducklake_catalog}', 
                'main', 
                '{table_name}', 
                '{start_time.isoformat()}', 
                '{end_time.isoformat()}'
            )
            ORDER BY snapshot_id DESC
        """
        
        return await self.execute_query(query)
    
    async def cleanup_old_files(self, dry_run: bool = True) -> List[Dict[str, Any]]:
        """Clean up old files in the DuckLake."""
        query = f"""
            SELECT * FROM ducklake_cleanup_old_files(
                '{self.ducklake_catalog}',
                dry_run => {str(dry_run).lower()}
            )
        """
        
        return await self.execute_query(query)
    
    async def close(self):
        """Close all connections in the pool."""
        for conn in self.connection_pool:
            conn.close()
        self.connection_pool.clear()
        self._initialized = False
        logger.info("DuckLake service closed")


# Global service instance
ducklake_service = DuckLakeService()
