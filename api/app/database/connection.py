"""DuckDB connection management for the API service."""

import os
import threading
from typing import Dict, Optional
import duckdb
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages DuckDB connections with thread-safe connection pooling."""
    
    _instance: Optional['DatabaseManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._connection_pool: Dict[int, duckdb.DuckDBPyConnection] = {}
            self._db_path = os.getenv("DUCKDB_PATH", "/app/data/ekko.db")
            self._pool_size = int(os.getenv("DUCKDB_POOL_SIZE", "10"))
            self._initialized = True
            self._ensure_data_directory()
    
    def _ensure_data_directory(self):
        """Ensure the data directory exists."""
        data_dir = os.path.dirname(self._db_path)
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"Database directory ensured: {data_dir}")
    
    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get a thread-safe database connection."""
        thread_id = threading.get_ident()
        
        if thread_id not in self._connection_pool:
            try:
                conn = duckdb.connect(self._db_path)
                self._init_connection(conn)
                self._connection_pool[thread_id] = conn
                logger.info(f"Created new DuckDB connection for thread {thread_id}")
            except Exception as e:
                logger.error(f"Failed to create DuckDB connection: {e}")
                raise
        
        return self._connection_pool[thread_id]
    
    def _init_connection(self, conn: duckdb.DuckDBPyConnection):
        """Initialize a new connection with required extensions and settings."""
        try:
            # Install and load required extensions
            conn.install_extension('json')
            conn.load_extension('json')
            
            # Set connection settings for better performance
            conn.execute("SET memory_limit='1GB'")
            conn.execute("SET threads=4")
            
            logger.info("DuckDB connection initialized with extensions")
        except Exception as e:
            logger.error(f"Failed to initialize DuckDB connection: {e}")
            raise
    
    def close_connection(self, thread_id: Optional[int] = None):
        """Close a specific connection or current thread's connection."""
        if thread_id is None:
            thread_id = threading.get_ident()
        
        if thread_id in self._connection_pool:
            try:
                self._connection_pool[thread_id].close()
                del self._connection_pool[thread_id]
                logger.info(f"Closed DuckDB connection for thread {thread_id}")
            except Exception as e:
                logger.error(f"Error closing DuckDB connection: {e}")
    
    def close_all_connections(self):
        """Close all connections in the pool."""
        for thread_id in list(self._connection_pool.keys()):
            self.close_connection(thread_id)
        logger.info("All DuckDB connections closed")
    
    @property
    def db_path(self) -> str:
        """Get the database file path."""
        return self._db_path
    
    def health_check(self) -> bool:
        """Check if the database is accessible."""
        try:
            conn = self.get_connection()
            result = conn.execute("SELECT 1").fetchone()
            return result[0] == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Get a database connection for the current thread."""
    return get_db_manager().get_connection()


@asynccontextmanager
async def get_db_session():
    """Async context manager for database sessions."""
    try:
        conn = get_db_connection()
        yield conn
    except Exception as e:
        logger.error(f"Database session error: {e}")
        raise
    finally:
        # Connection cleanup is handled by the manager
        pass
