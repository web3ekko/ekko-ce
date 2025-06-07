"""Database package for DuckDB integration."""

from .connection import DatabaseManager, get_db_connection
from .models import DatabaseSchema

__all__ = ["DatabaseManager", "get_db_connection", "DatabaseSchema"]
