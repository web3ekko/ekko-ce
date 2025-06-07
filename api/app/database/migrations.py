"""Database migration utilities."""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .connection import get_db_connection
from .models import DatabaseSchema

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database migrations and schema updates."""
    
    def __init__(self):
        self.db_connection = get_db_connection()
    
    def initialize_database(self):
        """Initialize the database with all required tables and indexes."""
        try:
            logger.info("Initializing database schema...")
            DatabaseSchema.create_all_tables(self.db_connection)
            logger.info("Database initialization completed successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            result = self.db_connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
                [table_name]
            ).fetchone()
            return result[0] > 0
        except Exception as e:
            logger.error(f"Error checking table existence for {table_name}: {e}")
            return False
    
    def get_table_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table."""
        try:
            if not self.check_table_exists(table_name):
                return 0
            
            result = self.db_connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            return result[0]
        except Exception as e:
            logger.error(f"Error getting row count for {table_name}: {e}")
            return 0
    
    def backup_table_to_json(self, table_name: str, backup_path: str):
        """Backup a table to a JSON file."""
        try:
            if not self.check_table_exists(table_name):
                logger.warning(f"Table {table_name} does not exist, skipping backup")
                return
            
            rows = self.db_connection.execute(f"SELECT * FROM {table_name}").fetchall()
            
            # Convert rows to list of dictionaries
            columns = [desc[0] for desc in self.db_connection.description]
            data = [dict(zip(columns, row)) for row in rows]
            
            # Convert datetime objects to strings for JSON serialization
            for row in data:
                for key, value in row.items():
                    if isinstance(value, datetime):
                        row[key] = value.isoformat()
            
            with open(backup_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Backed up {len(data)} rows from {table_name} to {backup_path}")
            
        except Exception as e:
            logger.error(f"Error backing up table {table_name}: {e}")
            raise
    
    def restore_table_from_json(self, table_name: str, backup_path: str):
        """Restore a table from a JSON backup file."""
        try:
            with open(backup_path, 'r') as f:
                data = json.load(f)
            
            if not data:
                logger.info(f"No data to restore for table {table_name}")
                return
            
            # Get column names from the first row
            columns = list(data[0].keys())
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join(columns)
            
            insert_sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
            
            # Prepare data for insertion
            rows_to_insert = []
            for row in data:
                row_values = [row.get(col) for col in columns]
                rows_to_insert.append(row_values)
            
            # Insert data in batches
            batch_size = 1000
            for i in range(0, len(rows_to_insert), batch_size):
                batch = rows_to_insert[i:i + batch_size]
                self.db_connection.executemany(insert_sql, batch)
            
            logger.info(f"Restored {len(rows_to_insert)} rows to {table_name}")
            
        except Exception as e:
            logger.error(f"Error restoring table {table_name}: {e}")
            raise
    
    def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate data integrity across all tables."""
        integrity_report = {
            "timestamp": datetime.now().isoformat(),
            "tables": {},
            "foreign_key_violations": [],
            "status": "unknown"
        }
        
        try:
            # Check each table
            schemas = DatabaseSchema.get_table_schemas()
            for table_name in schemas.keys():
                if self.check_table_exists(table_name):
                    row_count = self.get_table_row_count(table_name)
                    integrity_report["tables"][table_name] = {
                        "exists": True,
                        "row_count": row_count
                    }
                else:
                    integrity_report["tables"][table_name] = {
                        "exists": False,
                        "row_count": 0
                    }
            
            # Check foreign key constraints
            fk_violations = self._check_foreign_key_constraints()
            integrity_report["foreign_key_violations"] = fk_violations
            
            # Determine overall status
            if fk_violations:
                integrity_report["status"] = "violations_found"
            else:
                integrity_report["status"] = "healthy"
            
            logger.info(f"Data integrity validation completed: {integrity_report['status']}")
            
        except Exception as e:
            logger.error(f"Error during data integrity validation: {e}")
            integrity_report["status"] = "error"
            integrity_report["error"] = str(e)
        
        return integrity_report
    
    def _check_foreign_key_constraints(self) -> List[Dict[str, Any]]:
        """Check for foreign key constraint violations."""
        violations = []
        
        try:
            # Check alerts -> wallets
            if self.check_table_exists("alerts") and self.check_table_exists("wallets"):
                result = self.db_connection.execute("""
                    SELECT a.id, a.related_wallet_id 
                    FROM alerts a 
                    LEFT JOIN wallets w ON a.related_wallet_id = w.id 
                    WHERE a.related_wallet_id IS NOT NULL AND w.id IS NULL
                """).fetchall()
                
                for row in result:
                    violations.append({
                        "table": "alerts",
                        "column": "related_wallet_id",
                        "value": row[1],
                        "referencing_id": row[0]
                    })
            
            # Check wallet_balances -> wallets
            if self.check_table_exists("wallet_balances") and self.check_table_exists("wallets"):
                result = self.db_connection.execute("""
                    SELECT wb.id, wb.wallet_id 
                    FROM wallet_balances wb 
                    LEFT JOIN wallets w ON wb.wallet_id = w.id 
                    WHERE w.id IS NULL
                """).fetchall()
                
                for row in result:
                    violations.append({
                        "table": "wallet_balances",
                        "column": "wallet_id", 
                        "value": row[1],
                        "referencing_id": row[0]
                    })
            
            # Add more foreign key checks as needed
            
        except Exception as e:
            logger.error(f"Error checking foreign key constraints: {e}")
        
        return violations
    
    def reset_database(self):
        """Reset the database by dropping and recreating all tables."""
        try:
            logger.warning("Resetting database - all data will be lost!")
            DatabaseSchema.drop_all_tables(self.db_connection)
            DatabaseSchema.create_all_tables(self.db_connection)
            logger.info("Database reset completed successfully")
        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            raise
