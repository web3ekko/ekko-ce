"""
Direct DuckDB connection service with DuckLake extension.

DuckLake is a lakehouse format that uses:
- A catalog database (DuckDB/PostgreSQL/SQLite) for metadata
- Parquet files for data storage
- Features: schema evolution, time travel, snapshots

Requires DuckDB 1.3.0+

This complements the existing `ducklake_client.py` which proxies queries
through NATS to wasmCloud providers.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.conf import settings

try:
    import duckdb  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    duckdb = None

logger = logging.getLogger(__name__)


@dataclass
class DuckLakeConfig:
    """DuckLake connection configuration."""

    # Catalog type: 'duckdb', 'postgresql', 'sqlite'
    catalog_type: str = "duckdb"
    # Path to catalog metadata file (for duckdb/sqlite types)
    metadata_path: str = "metadata.ducklake"
    # Path to Parquet data files (local or S3)
    data_path: str = "data/"
    # PostgreSQL connection string (if using postgres catalog)
    postgres_dsn: Optional[str] = None
    # Catalog name when attached
    catalog_name: str = "ekko_lake"
    # Performance settings
    threads: int = 4
    memory_limit: str = "2GB"


class DuckLakeService:
    """
    Direct DuckDB connection service with DuckLake extension.

    Features:
    - Thread-local connections for Django's multi-threaded environment
    - DuckLake catalog attachment (supports DuckDB, PostgreSQL, SQLite backends)
    - Parameterized queries for security
    - Snapshot/time travel support
    - Health monitoring
    """

    _instance: Optional["DuckLakeService"] = None
    _lock = threading.Lock()
    _local = threading.local()

    def __new__(cls) -> "DuckLakeService":
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._config = self._load_config()
        self._initialized = True
        logger.info(
            f"DuckLake service initialized: catalog={self._config.catalog_name}"
        )

    def _load_config(self) -> DuckLakeConfig:
        """Load configuration from Django settings."""
        return DuckLakeConfig(
            catalog_type=getattr(settings, "DUCKLAKE_CATALOG_TYPE", "duckdb"),
            metadata_path=getattr(
                settings, "DUCKLAKE_METADATA_PATH", "metadata.ducklake"
            ),
            data_path=getattr(settings, "DUCKLAKE_DATA_PATH", "data/"),
            postgres_dsn=getattr(settings, "DUCKLAKE_POSTGRES_DSN", None),
            catalog_name=getattr(settings, "DUCKLAKE_CATALOG_NAME", "ekko_lake"),
            threads=getattr(settings, "DUCKLAKE_THREADS", 4),
            memory_limit=getattr(settings, "DUCKLAKE_MEMORY_LIMIT", "2GB"),
        )

    def _get_connection(self):
        """Get thread-local DuckDB connection with DuckLake attached."""
        if duckdb is None:
            raise RuntimeError(
                "DuckDB is not installed. Install the 'duckdb' Python package to use DuckLake analytics endpoints."
            )

        if not hasattr(self._local, "connection") or self._local.connection is None:
            # Create in-memory DuckDB connection
            conn = duckdb.connect(":memory:")

            # Configure connection
            conn.execute(f"SET threads = {self._config.threads}")
            conn.execute(f"SET memory_limit = '{self._config.memory_limit}'")

            # Install and load DuckLake extension
            conn.execute("INSTALL ducklake")
            conn.execute("LOAD ducklake")

            # Attach DuckLake catalog based on catalog type
            self._attach_ducklake_catalog(conn)

            self._local.connection = conn
            logger.debug("Created new DuckDB connection with DuckLake attached")

        return self._local.connection

    def _attach_ducklake_catalog(self, conn) -> None:
        """Attach DuckLake catalog based on configuration."""
        cfg = self._config
        catalog_name = cfg.catalog_name

        if cfg.catalog_type == "duckdb":
            # DuckDB file-based catalog
            conn.execute(
                f"""
                ATTACH 'ducklake:{cfg.metadata_path}' AS {catalog_name}
                (DATA_PATH '{cfg.data_path}')
            """
            )
        elif cfg.catalog_type == "sqlite":
            # SQLite-based catalog
            conn.execute("INSTALL sqlite")
            conn.execute("LOAD sqlite")
            conn.execute(
                f"""
                ATTACH 'ducklake:sqlite:{cfg.metadata_path}' AS {catalog_name}
                (DATA_PATH '{cfg.data_path}')
            """
            )
        elif cfg.catalog_type == "postgresql":
            # PostgreSQL-based catalog
            if not cfg.postgres_dsn:
                raise ValueError("PostgreSQL catalog requires DUCKLAKE_POSTGRES_DSN")
            conn.execute("INSTALL postgres")
            conn.execute("LOAD postgres")
            conn.execute(
                f"""
                ATTACH 'ducklake:postgres:{cfg.postgres_dsn}' AS {catalog_name}
                (DATA_PATH '{cfg.data_path}')
            """
            )
        else:
            raise ValueError(f"Unsupported catalog type: {cfg.catalog_type}")

        # Use the DuckLake catalog by default
        conn.execute(f"USE {catalog_name}")
        logger.info(
            f"Attached DuckLake catalog: {catalog_name} (type={cfg.catalog_type})"
        )

    @contextmanager
    def connection(self):
        """Context manager for connection access."""
        conn = self._get_connection()
        try:
            yield conn
        except Exception as e:
            logger.error(f"DuckLake query error: {e}")
            raise

    def query(
        self, sql: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as list of dicts.

        Args:
            sql: SQL query with $param placeholders
            params: Query parameters

        Returns:
            List of result rows as dictionaries
        """
        with self.connection() as conn:
            if params:
                result = conn.execute(sql, params)
            else:
                result = conn.execute(sql)

            if result.description is None:
                return []

            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()

            return [dict(zip(columns, row)) for row in rows]

    def query_df(self, sql: str, params: Optional[Dict[str, Any]] = None):
        """Execute query and return as Polars DataFrame."""
        with self.connection() as conn:
            if params:
                result = conn.execute(sql, params)
            else:
                result = conn.execute(sql)

            return result.pl()

    def execute(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Execute SQL statement without returning results."""
        with self.connection() as conn:
            if params:
                conn.execute(sql, params)
            else:
                conn.execute(sql)

    def get_snapshots(self) -> List[Dict[str, Any]]:
        """Get all available DuckLake snapshots for time travel."""
        with self.connection() as conn:
            result = conn.execute(f"FROM {self._config.catalog_name}.snapshots()")
            if result.description is None:
                return []
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def query_at_snapshot(
        self, sql: str, snapshot_id: int, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute query at a specific snapshot (time travel)."""
        with self.connection() as conn:
            # Set snapshot for time travel
            conn.execute(f"SET ducklake_snapshot_id = {snapshot_id}")
            try:
                if params:
                    result = conn.execute(sql, params)
                else:
                    result = conn.execute(sql)

                if result.description is None:
                    return []

                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            finally:
                # Reset to current snapshot
                conn.execute("RESET ducklake_snapshot_id")

    def get_tables(self) -> List[str]:
        """Get list of tables in the DuckLake catalog."""
        with self.connection() as conn:
            result = conn.execute(
                f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_catalog = '{self._config.catalog_name}'
            """
            )
            rows = result.fetchall()
            return [row[0] for row in rows]

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema information for a table."""
        with self.connection() as conn:
            result = conn.execute(
                f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_catalog = '{self._config.catalog_name}'
                  AND table_name = '{table_name}'
                ORDER BY ordinal_position
            """
            )
            columns = ["column_name", "data_type", "is_nullable"]
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        try:
            with self.connection() as conn:
                conn.execute("SELECT 1 as health").fetchone()

                # Get table info from DuckLake catalog
                tables = self.get_tables()

                return {
                    "status": "healthy",
                    "catalog_name": self._config.catalog_name,
                    "catalog_type": self._config.catalog_type,
                    "data_path": self._config.data_path,
                    "tables": tables,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def close(self) -> None:
        """Close the thread-local connection."""
        if hasattr(self._local, "connection") and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None
            logger.debug("Closed DuckDB connection")


def get_ducklake_service() -> DuckLakeService:
    """Get the DuckLake service singleton."""
    return DuckLakeService()
