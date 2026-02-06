"""Tests for DuckLake service.

Unit tests for the direct DuckDB/DuckLake connection service.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import threading

from app.services.duckdb_service import (
    DuckLakeService,
    DuckLakeConfig,
    get_ducklake_service,
)


class TestDuckLakeConfig:
    """Test DuckLakeConfig dataclass."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = DuckLakeConfig()

        assert config.catalog_type == "duckdb"
        assert config.metadata_path == "metadata.ducklake"
        assert config.data_path == "data/"
        assert config.postgres_dsn is None
        assert config.catalog_name == "ekko_lake"
        assert config.threads == 4
        assert config.memory_limit == "2GB"

    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = DuckLakeConfig(
            catalog_type="postgresql",
            metadata_path="/data/meta.ducklake",
            data_path="s3://bucket/data/",
            postgres_dsn="dbname=test host=localhost",
            catalog_name="custom_lake",
            threads=8,
            memory_limit="4GB",
        )

        assert config.catalog_type == "postgresql"
        assert config.metadata_path == "/data/meta.ducklake"
        assert config.data_path == "s3://bucket/data/"
        assert config.postgres_dsn == "dbname=test host=localhost"
        assert config.catalog_name == "custom_lake"
        assert config.threads == 8
        assert config.memory_limit == "4GB"


class TestDuckLakeServiceSingleton:
    """Test singleton pattern of DuckLakeService."""

    def setup_method(self):
        """Reset singleton before each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    def teardown_method(self):
        """Clean up after each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    @patch("app.services.duckdb_service.duckdb")
    def test_singleton_pattern(self, mock_duckdb):
        """Test that service uses singleton pattern."""
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        service1 = get_ducklake_service()
        service2 = get_ducklake_service()

        assert service1 is service2

    @patch("app.services.duckdb_service.duckdb")
    def test_singleton_threadsafe(self, mock_duckdb):
        """Test singleton is thread-safe."""
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        services = []
        errors = []

        def get_service():
            try:
                services.append(get_ducklake_service())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_service) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(services) == 10
        # All should be the same instance
        assert all(s is services[0] for s in services)


class TestDuckLakeServiceConfiguration:
    """Test DuckLakeService configuration loading."""

    def setup_method(self):
        """Reset singleton before each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    def teardown_method(self):
        """Clean up after each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    @patch("app.services.duckdb_service.duckdb")
    @patch("app.services.duckdb_service.settings")
    def test_loads_config_from_settings(self, mock_settings, mock_duckdb):
        """Test configuration is loaded from Django settings."""
        mock_settings.DUCKLAKE_CATALOG_TYPE = "postgresql"
        mock_settings.DUCKLAKE_METADATA_PATH = "/custom/path.ducklake"
        mock_settings.DUCKLAKE_DATA_PATH = "/custom/data/"
        mock_settings.DUCKLAKE_POSTGRES_DSN = "dbname=mydb"
        mock_settings.DUCKLAKE_CATALOG_NAME = "my_catalog"
        mock_settings.DUCKLAKE_THREADS = 16
        mock_settings.DUCKLAKE_MEMORY_LIMIT = "8GB"

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        service = DuckLakeService()

        assert service._config.catalog_type == "postgresql"
        assert service._config.metadata_path == "/custom/path.ducklake"
        assert service._config.data_path == "/custom/data/"
        assert service._config.postgres_dsn == "dbname=mydb"
        assert service._config.catalog_name == "my_catalog"
        assert service._config.threads == 16
        assert service._config.memory_limit == "8GB"


class TestDuckLakeServiceCatalogAttachment:
    """Test DuckLake catalog attachment logic."""

    def setup_method(self):
        """Reset singleton before each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    def teardown_method(self):
        """Clean up after each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    @patch("app.services.duckdb_service.duckdb")
    def test_duckdb_catalog_attachment(self, mock_duckdb):
        """Test DuckDB file-based catalog attachment."""
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        service = get_ducklake_service()
        # Force connection to be created
        service._get_connection()

        # Verify ducklake extension was installed and loaded
        calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any("INSTALL ducklake" in call for call in calls)
        assert any("LOAD ducklake" in call for call in calls)
        # Verify ATTACH was called with ducklake: prefix
        assert any("ATTACH" in call and "ducklake:" in call for call in calls)

    @patch("app.services.duckdb_service.settings")
    @patch("app.services.duckdb_service.duckdb")
    def test_postgresql_catalog_attachment(self, mock_duckdb, mock_settings):
        """Test PostgreSQL-based catalog attachment."""
        mock_settings.DUCKLAKE_CATALOG_TYPE = "postgresql"
        mock_settings.DUCKLAKE_POSTGRES_DSN = "dbname=mydb host=localhost"
        mock_settings.DUCKLAKE_METADATA_PATH = "metadata.ducklake"
        mock_settings.DUCKLAKE_DATA_PATH = "data/"
        mock_settings.DUCKLAKE_CATALOG_NAME = "ekko_lake"
        mock_settings.DUCKLAKE_THREADS = 4
        mock_settings.DUCKLAKE_MEMORY_LIMIT = "2GB"

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        service = DuckLakeService()
        service._get_connection()

        # Verify postgres extension was installed
        calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any("INSTALL postgres" in call for call in calls)
        assert any("LOAD postgres" in call for call in calls)
        # Verify ATTACH was called with ducklake:postgres: prefix
        assert any("ducklake:postgres:" in call for call in calls)

    @patch("app.services.duckdb_service.settings")
    @patch("app.services.duckdb_service.duckdb")
    def test_postgresql_without_dsn_raises_error(self, mock_duckdb, mock_settings):
        """Test PostgreSQL catalog without DSN raises ValueError."""
        mock_settings.DUCKLAKE_CATALOG_TYPE = "postgresql"
        mock_settings.DUCKLAKE_POSTGRES_DSN = None
        mock_settings.DUCKLAKE_METADATA_PATH = "metadata.ducklake"
        mock_settings.DUCKLAKE_DATA_PATH = "data/"
        mock_settings.DUCKLAKE_CATALOG_NAME = "ekko_lake"
        mock_settings.DUCKLAKE_THREADS = 4
        mock_settings.DUCKLAKE_MEMORY_LIMIT = "2GB"

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        service = DuckLakeService()

        with pytest.raises(ValueError, match="PostgreSQL catalog requires"):
            service._get_connection()

    @patch("app.services.duckdb_service.settings")
    @patch("app.services.duckdb_service.duckdb")
    def test_sqlite_catalog_attachment(self, mock_duckdb, mock_settings):
        """Test SQLite-based catalog attachment."""
        mock_settings.DUCKLAKE_CATALOG_TYPE = "sqlite"
        mock_settings.DUCKLAKE_METADATA_PATH = "metadata.db"
        mock_settings.DUCKLAKE_DATA_PATH = "data/"
        mock_settings.DUCKLAKE_POSTGRES_DSN = None
        mock_settings.DUCKLAKE_CATALOG_NAME = "ekko_lake"
        mock_settings.DUCKLAKE_THREADS = 4
        mock_settings.DUCKLAKE_MEMORY_LIMIT = "2GB"

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        service = DuckLakeService()
        service._get_connection()

        # Verify sqlite extension was installed
        calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any("INSTALL sqlite" in call for call in calls)
        assert any("ducklake:sqlite:" in call for call in calls)

    @patch("app.services.duckdb_service.settings")
    @patch("app.services.duckdb_service.duckdb")
    def test_unsupported_catalog_type_raises_error(self, mock_duckdb, mock_settings):
        """Test unsupported catalog type raises ValueError."""
        mock_settings.DUCKLAKE_CATALOG_TYPE = "mysql"  # Not supported
        mock_settings.DUCKLAKE_POSTGRES_DSN = None
        mock_settings.DUCKLAKE_METADATA_PATH = "metadata.ducklake"
        mock_settings.DUCKLAKE_DATA_PATH = "data/"
        mock_settings.DUCKLAKE_CATALOG_NAME = "ekko_lake"
        mock_settings.DUCKLAKE_THREADS = 4
        mock_settings.DUCKLAKE_MEMORY_LIMIT = "2GB"

        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        service = DuckLakeService()

        with pytest.raises(ValueError, match="Unsupported catalog type"):
            service._get_connection()


class TestDuckLakeServiceQuery:
    """Test DuckLakeService query methods."""

    def setup_method(self):
        """Reset singleton before each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    def teardown_method(self):
        """Clean up after each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    @patch("app.services.duckdb_service.duckdb")
    def test_query_returns_list_of_dicts(self, mock_duckdb):
        """Test query returns results as list of dictionaries."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.description = [("id",), ("name",), ("value",)]
        mock_result.fetchall.return_value = [
            (1, "test1", 100),
            (2, "test2", 200),
        ]
        mock_conn.execute.return_value = mock_result
        mock_duckdb.connect.return_value = mock_conn

        service = get_ducklake_service()
        results = service.query("SELECT * FROM test")

        assert len(results) == 2
        assert results[0] == {"id": 1, "name": "test1", "value": 100}
        assert results[1] == {"id": 2, "name": "test2", "value": 200}

    @patch("app.services.duckdb_service.duckdb")
    def test_query_with_params(self, mock_duckdb):
        """Test query with parameters."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.description = [("id",), ("name",)]
        mock_result.fetchall.return_value = [(1, "filtered")]
        mock_conn.execute.return_value = mock_result
        mock_duckdb.connect.return_value = mock_conn

        service = get_ducklake_service()
        results = service.query(
            "SELECT * FROM test WHERE id = $id", params={"id": 1}
        )

        assert len(results) == 1
        assert results[0] == {"id": 1, "name": "filtered"}
        # Verify params were passed to execute
        mock_conn.execute.assert_called_with(
            "SELECT * FROM test WHERE id = $id", {"id": 1}
        )

    @patch("app.services.duckdb_service.duckdb")
    def test_query_with_no_results(self, mock_duckdb):
        """Test query with no results."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.description = [("id",), ("name",)]
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_duckdb.connect.return_value = mock_conn

        service = get_ducklake_service()
        results = service.query("SELECT * FROM empty_table")

        assert results == []

    @patch("app.services.duckdb_service.duckdb")
    def test_query_with_null_description(self, mock_duckdb):
        """Test query with None description (INSERT/UPDATE)."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.description = None
        mock_conn.execute.return_value = mock_result
        mock_duckdb.connect.return_value = mock_conn

        service = get_ducklake_service()
        results = service.query("INSERT INTO test VALUES (1)")

        assert results == []


class TestDuckLakeServiceSnapshots:
    """Test DuckLakeService snapshot/time travel methods."""

    def setup_method(self):
        """Reset singleton before each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    def teardown_method(self):
        """Clean up after each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    @patch("app.services.duckdb_service.duckdb")
    def test_get_snapshots(self, mock_duckdb):
        """Test get_snapshots returns snapshot list."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.description = [("snapshot_id",), ("created_at",)]
        mock_result.fetchall.return_value = [
            (1, "2024-01-01 00:00:00"),
            (2, "2024-01-02 00:00:00"),
        ]
        mock_conn.execute.return_value = mock_result
        mock_duckdb.connect.return_value = mock_conn

        service = get_ducklake_service()
        snapshots = service.get_snapshots()

        assert len(snapshots) == 2
        assert snapshots[0]["snapshot_id"] == 1
        assert snapshots[1]["snapshot_id"] == 2

    @patch("app.services.duckdb_service.duckdb")
    def test_query_at_snapshot(self, mock_duckdb):
        """Test query_at_snapshot sets and resets snapshot."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.description = [("id",), ("value",)]
        mock_result.fetchall.return_value = [(1, "historical")]
        mock_conn.execute.return_value = mock_result
        mock_duckdb.connect.return_value = mock_conn

        service = get_ducklake_service()
        results = service.query_at_snapshot(
            "SELECT * FROM test", snapshot_id=42
        )

        assert len(results) == 1
        assert results[0] == {"id": 1, "value": "historical"}

        # Verify SET and RESET were called
        calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any("SET ducklake_snapshot_id = 42" in call for call in calls)
        assert any("RESET ducklake_snapshot_id" in call for call in calls)


class TestDuckLakeServiceHealthCheck:
    """Test DuckLakeService health check."""

    def setup_method(self):
        """Reset singleton before each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    def teardown_method(self):
        """Clean up after each test."""
        DuckLakeService._instance = None
        if hasattr(DuckLakeService._local, "connection"):
            DuckLakeService._local.connection = None

    @patch("app.services.duckdb_service.duckdb")
    def test_health_check_healthy(self, mock_duckdb):
        """Test health check returns healthy status."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_result.description = [("table_name",)]
        mock_result.fetchall.return_value = [("transactions",), ("blocks",)]
        mock_conn.execute.return_value = mock_result
        mock_duckdb.connect.return_value = mock_conn

        service = get_ducklake_service()
        health = service.health_check()

        assert health["status"] == "healthy"
        assert "catalog_name" in health
        assert "catalog_type" in health
        assert "data_path" in health
        assert "tables" in health

    @patch("app.services.duckdb_service.duckdb")
    def test_health_check_unhealthy(self, mock_duckdb):
        """Test health check returns unhealthy status on error."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Connection failed")
        mock_duckdb.connect.return_value = mock_conn

        service = get_ducklake_service()
        health = service.health_check()

        assert health["status"] == "unhealthy"
        assert "error" in health
