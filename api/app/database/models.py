"""Database schema definitions for DuckDB tables."""

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class DatabaseSchema:
    """Manages database schema creation and migrations."""
    
    @staticmethod
    def get_table_schemas() -> Dict[str, str]:
        """Get all table creation SQL statements."""
        return {
            "users": """
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR PRIMARY KEY,
                    email VARCHAR UNIQUE NOT NULL,
                    full_name VARCHAR NOT NULL,
                    role VARCHAR DEFAULT 'user',
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    hashed_password VARCHAR NOT NULL
                )
            """,
            
            "wallets": """
                CREATE TABLE IF NOT EXISTS wallets (
                    id VARCHAR PRIMARY KEY,
                    blockchain_symbol VARCHAR NOT NULL,
                    address VARCHAR NOT NULL,
                    name VARCHAR NOT NULL,
                    balance DECIMAL(24,8) DEFAULT 0,
                    status VARCHAR DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE(blockchain_symbol, address)
                )
            """,
            
            "alerts": """
                CREATE TABLE IF NOT EXISTS alerts (
                    id VARCHAR PRIMARY KEY,
                    type VARCHAR NOT NULL,
                    message VARCHAR NOT NULL,
                    time VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    icon VARCHAR,
                    priority VARCHAR,
                    related_wallet_id VARCHAR,
                    query VARCHAR,
                    job_spec JSON,
                    notifications_enabled BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (related_wallet_id) REFERENCES wallets(id)
                )
            """,
            
            "wallet_balances": """
                CREATE TABLE IF NOT EXISTS wallet_balances (
                    id VARCHAR PRIMARY KEY,
                    wallet_id VARCHAR NOT NULL,
                    timestamp VARCHAR NOT NULL,
                    balance DECIMAL(24,8) NOT NULL,
                    token_price DECIMAL(24,8),
                    fiat_value DECIMAL(24,8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (wallet_id) REFERENCES wallets(id)
                )
            """,
            
            "alert_rules": """
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    description VARCHAR,
                    condition JSON NOT NULL,
                    action JSON NOT NULL,
                    enabled BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    created_by VARCHAR NOT NULL,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            """,
            
            "workflows": """
                CREATE TABLE IF NOT EXISTS workflows (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    description VARCHAR,
                    steps JSON NOT NULL,
                    enabled BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    created_by VARCHAR NOT NULL,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            """,
            
            "workflow_executions": """
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    id VARCHAR PRIMARY KEY,
                    workflow_id VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    result JSON,
                    error_message VARCHAR,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
                )
            """,
            
            "agents": """
                CREATE TABLE IF NOT EXISTS agents (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    type VARCHAR NOT NULL,
                    config JSON NOT NULL,
                    max_budget DECIMAL(24,8) DEFAULT 0,
                    status VARCHAR DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    created_by VARCHAR NOT NULL,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )
            """
        }
    
    @staticmethod
    def get_indexes() -> List[str]:
        """Get index creation SQL statements for performance optimization."""
        return [
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_wallets_blockchain_address ON wallets(blockchain_symbol, address)",
            "CREATE INDEX IF NOT EXISTS idx_wallets_status ON wallets(status)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_wallet_id ON alerts(related_wallet_id)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_wallet_balances_wallet_id ON wallet_balances(wallet_id)",
            "CREATE INDEX IF NOT EXISTS idx_wallet_balances_timestamp ON wallet_balances(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_alert_rules_created_by ON alert_rules(created_by)",
            "CREATE INDEX IF NOT EXISTS idx_workflows_enabled ON workflows(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_workflows_created_by ON workflows(created_by)",
            "CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_id ON workflow_executions(workflow_id)",
            "CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status)",
            "CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)",
            "CREATE INDEX IF NOT EXISTS idx_agents_created_by ON agents(created_by)"
        ]
    
    @classmethod
    def create_all_tables(cls, connection):
        """Create all tables in the correct dependency order."""
        schemas = cls.get_table_schemas()
        
        # Create tables in dependency order
        table_order = [
            "users",
            "wallets", 
            "alerts",
            "wallet_balances",
            "alert_rules",
            "workflows",
            "workflow_executions",
            "agents"
        ]
        
        try:
            for table_name in table_order:
                if table_name in schemas:
                    logger.info(f"Creating table: {table_name}")
                    connection.execute(schemas[table_name])
                    logger.info(f"Table {table_name} created successfully")
            
            # Create indexes
            logger.info("Creating database indexes...")
            for index_sql in cls.get_indexes():
                connection.execute(index_sql)
            
            logger.info("All database tables and indexes created successfully")
            
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    @classmethod
    def drop_all_tables(cls, connection):
        """Drop all tables (for testing/reset purposes)."""
        schemas = cls.get_table_schemas()
        
        # Drop in reverse dependency order
        table_order = [
            "agents",
            "workflow_executions", 
            "workflows",
            "alert_rules",
            "wallet_balances",
            "alerts",
            "wallets",
            "users"
        ]
        
        try:
            for table_name in table_order:
                if table_name in schemas:
                    logger.info(f"Dropping table: {table_name}")
                    connection.execute(f"DROP TABLE IF EXISTS {table_name}")
            
            logger.info("All database tables dropped successfully")
            
        except Exception as e:
            logger.error(f"Error dropping database tables: {e}")
            raise
