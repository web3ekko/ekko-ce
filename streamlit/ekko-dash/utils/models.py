import duckdb
import uuid
from datetime import datetime
import redis
import streamlit as st
import os
from urllib.parse import urlparse
from typing import Optional, Dict, Any
from src.config.settings import Settings
from typing import Optional, Dict, Any, List
import logging

class Database:
    _instance: Optional['Database'] = None
    _connection_pool: Dict[int, duckdb.DuckDBPyConnection] = {}
    
    def __init__(self, settings) -> None:
        """Initialize database with settings"""
        self.settings = settings
        if not hasattr(self, '_initialized'):
            self._init_database()
            self._initialized = True
    
    def _init_database(self) -> None:
        """Initialize database and create tables"""
        try:
            # Create data directory if it doesn't exist
            import os
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
            os.makedirs(data_dir, exist_ok=True)
            
            # Get initial connection and install extensions
            conn = self.get_connection()
            self._init_connection(conn)
            
            # Create tables in correct order
            self.create_tables()
            
            # Populate initial data
            self.populate_blockchain_table()
        except Exception as e:
            st.error(f"Failed to initialize database: {str(e)}")
            raise
    
    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get a database connection from the pool"""
        import threading
        import os
        thread_id = threading.get_ident()
        
        if thread_id not in self._connection_pool:
            db_settings = self.settings.database
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
            db_path = os.path.join(data_dir, db_settings.get('path', 'ekko.db'))
            conn = duckdb.connect(db_path)
            self._connection_pool[thread_id] = conn
        
        return self._connection_pool[thread_id]
    
    def _init_connection(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Initialize a new connection with required extensions"""
        try:
            conn.install_extension('json')
            conn.install_extension('httpfs')
            conn.load_extension('json')
            conn.load_extension('httpfs')
        except Exception as e:
            st.error(f"Failed to initialize database extensions: {str(e)}")
            raise

    def create_tables(self) -> None:
        """Create all database tables in the correct order"""
        try:
            # Create tables in dependency order
            st.write("Creating blockchain table...")
            self.create_blockchain_table()
            
            st.write("Creating wallet table...")
            self.create_wallet_table()
            
            st.write("Creating alert table...")
            self.create_alert_table()
            
            st.write("Creating workflow table...")
            self.create_workflow_table()
            
            st.write("Creating agent table...")
            self.create_agent_table()
            
            st.write("Creating settings table...")
            self.create_settings_table()
            
            st.write("Creating notification services table...")
            self.create_notification_service_table()
            
            st.write("All tables created successfully!")
        except Exception as e:
            st.error(f"Failed to create tables: {str(e)}")
            raise

    def populate_blockchain_table(self) -> None:
        """Populate blockchain table with default chains if empty"""
        try:
            # Check if the table is empty
            count_query = "SELECT COUNT(*) FROM blockchain"
            count_result = self.get_connection().execute(count_query).fetchone()[0]
            
            if count_result == 0:
                # Insert default blockchains
                insert_query = """
                INSERT INTO blockchain (id, name, symbol, chain_type) VALUES
                (?, 'Ethereum', 'ETH', 'EVM'),
                (?, 'Avalanche', 'AVAX', 'EVM'),
                (?, 'Polygon', 'MATIC', 'EVM'),
                (?, 'Bitcoin', 'BTC', 'UTXO')
                """
                self.get_connection().execute(insert_query, (
                    uuid.uuid4(),  # UUID type, not string
                    uuid.uuid4(),
                    uuid.uuid4(),
                    uuid.uuid4()
                ))
        except Exception as e:
            st.error(f"Failed to populate blockchain table: {str(e)}")
            raise

    def create_blockchain_table(self) -> None:
        """Create blockchain table - this must be created first"""
        try:
            query = """
            CREATE TABLE IF NOT EXISTS blockchain (
                id UUID PRIMARY KEY,
                name VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL UNIQUE,
                chain_type VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            self.get_connection().execute(query)
        except Exception as e:
            st.error(f"Failed to create blockchain table: {str(e)}")
            raise

    def create_wallet_table(self) -> None:
        """Create wallet table - depends on blockchain table"""
        try:
            query = """
            CREATE TABLE IF NOT EXISTS wallet (
                id UUID PRIMARY KEY,
                blockchain_symbol VARCHAR NOT NULL,
                address VARCHAR NOT NULL,
                name VARCHAR,
                balance DECIMAL(24,8) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (blockchain_symbol) REFERENCES blockchain(symbol),
                UNIQUE (blockchain_symbol, address)
            )
            """
            self.get_connection().execute(query)
        except Exception as e:
            st.error(f"Failed to create wallet table: {str(e)}")
            raise

    def create_alert_table(self) -> None:
        """Create alert table - depends on wallet table"""
        try:
            query = """
            CREATE TABLE IF NOT EXISTS alert (
                id UUID PRIMARY KEY,
                wallet_id UUID NOT NULL,
                blockchain_symbol VARCHAR NOT NULL,
                type VARCHAR NOT NULL,
                condition VARCHAR NOT NULL,
                threshold DECIMAL(24,8),
                status VARCHAR DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_triggered TIMESTAMP,
                notification_topic VARCHAR,
                FOREIGN KEY (wallet_id) REFERENCES wallet(id),
                FOREIGN KEY (blockchain_symbol) REFERENCES blockchain(symbol)
            )
            """
            self.get_connection().execute(query)
        except Exception as e:
            st.error(f"Failed to create alert table: {str(e)}")
            raise

    def create_workflow_table(self) -> None:
        """Create workflow table - independent table"""
        try:
            query = """
            CREATE TABLE IF NOT EXISTS workflow (
                id UUID PRIMARY KEY,
                name VARCHAR NOT NULL,
                description TEXT,
                trigger_type VARCHAR NOT NULL,
                trigger_condition VARCHAR NOT NULL,
                action_type VARCHAR NOT NULL,
                action_params JSON,
                status VARCHAR DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_run TIMESTAMP
            )
            """
            self.get_connection().execute(query)
        except Exception as e:
            st.error(f"Failed to create workflow table: {str(e)}")
            raise

    def create_agent_table(self) -> None:
        """Create agent table - independent table"""
        try:
            query = """
            CREATE TABLE IF NOT EXISTS agent (
                id UUID PRIMARY KEY,
                name VARCHAR NOT NULL,
                type VARCHAR NOT NULL,
                config JSON,
                max_budget DECIMAL(24,8) DEFAULT 0,
                status VARCHAR DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP
            )
            """
            self.get_connection().execute(query)
        except Exception as e:
            st.error(f"Failed to create agent table: {str(e)}")
            raise

    def create_settings_table(self) -> None:
        """Create settings table - independent table"""
        try:
            query = """
            CREATE TABLE IF NOT EXISTS settings (
                id UUID PRIMARY KEY,
                key VARCHAR NOT NULL UNIQUE,
                value JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
            self.get_connection().execute(query)
        except Exception as e:
            st.error(f"Failed to create settings table: {str(e)}")
            raise

    def create_notification_service_table(self) -> None:
        """Create notification_service table to store user endpoints"""
        try:
            query = """
            CREATE TABLE IF NOT EXISTS notification_service (
                id UUID PRIMARY KEY,
                type VARCHAR NOT NULL,
                url VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            self.get_connection().execute(query)
        except Exception as e:
            st.error(f"Failed to create notification_service table: {str(e)}")
            raise

    def install_extensions(self) -> None:
        """Install and load required DuckDB extensions"""
        conn = self.get_connection()
        
        # Core extensions
        extensions = [
            'json',
            ('tsid', 'community'),  # From community
            'httpfs',
            'sqlite',
            'postgres',
            'aws',
            'inet',
            'icu',
            'tpch',
            'tpcds',
            'excel',
            'parquet',
            'arrow',
            'json_experimental'
        ]
        
        for ext in extensions:
            try:
                if isinstance(ext, tuple):
                    name, source = ext
                    conn.execute(f"INSTALL {name} FROM {source}")
                    conn.execute(f"LOAD {name}")
                else:
                    conn.execute(f"INSTALL {ext}")
                    conn.execute(f"LOAD {ext}")
            except Exception as e:
                st.warning(f"Failed to install/load extension {ext}: {e}")

class Blockchain:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, blockchain_data: Dict[str, str]) -> None:
        query = """
        INSERT INTO blockchain (id, name, symbol, chain_type)
        VALUES (?, ?, ?, ?)
        """
        self.db.get_connection().execute(query, [
            uuid.uuid4(),  # UUID type, not string
            blockchain_data['name'],
            blockchain_data['symbol'],
            blockchain_data.get('chain_type', 'unknown')
        ])

    def get_all(self) -> List[Dict[str, Any]]:
        # Return raw rows for blockchain list
        return self.db.get_connection().execute(
            "SELECT * FROM blockchain ORDER BY name"
        ).fetchall()
    
    def get_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        result = self.db.get_connection().execute(
            "SELECT * FROM blockchain WHERE symbol = ?", [symbol]
        ).fetchone()
        return dict(result) if result else None

class Wallet:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, wallet_data: Dict[str, Any]) -> None:
        query = """
        INSERT INTO wallet (id, blockchain_symbol, address, name, balance)
        VALUES (?, ?, ?, ?, ?)
        """
        self.db.get_connection().execute(query, [
            uuid.uuid4(),  # UUID type, not string
            wallet_data['blockchain_symbol'],
            wallet_data['address'].lower(),  # Store addresses in lowercase
            wallet_data.get('name'),
            wallet_data.get('balance', 0)
        ])

    def get_all(self) -> List[Dict[str, Any]]:
        # Return raw rows for wallet list
        return self.db.get_connection().execute("""
            SELECT w.*, b.name as blockchain_name 
            FROM wallet w 
            JOIN blockchain b ON w.blockchain_symbol = b.symbol
            ORDER BY w.created_at DESC
        """).fetchall()
    
    def get_by_blockchain(self, blockchain_symbol: str) -> List[Dict[str, Any]]:
        result = self.db.get_connection().execute("""
            SELECT w.*, b.name as blockchain_name 
            FROM wallet w 
            JOIN blockchain b ON w.blockchain_symbol = b.symbol
            WHERE w.blockchain_symbol = ?
            ORDER BY w.created_at DESC
        """, [blockchain_symbol]).fetchall()
        return [dict(row) for row in result]
    
    def get_by_address(self, blockchain_symbol: str, address: str) -> Optional[Dict[str, Any]]:
        result = self.db.get_connection().execute("""
            SELECT w.*, b.name as blockchain_name 
            FROM wallet w 
            JOIN blockchain b ON w.blockchain_symbol = b.symbol
            WHERE w.blockchain_symbol = ? AND w.address = ?
        """, [blockchain_symbol, address.lower()]).fetchone()
        return dict(result) if result else None
    
    def update_balance(self, blockchain_symbol: str, address: str, new_balance: float) -> None:
        self.db.get_connection().execute("""
            UPDATE wallet 
            SET balance = ?, updated_at = CURRENT_TIMESTAMP
            WHERE blockchain_symbol = ? AND address = ?
        """, [
            new_balance,
            blockchain_symbol,
            address.lower()
        ])

class Alert:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, alert_data: Dict[str, Any]) -> None:
        """Insert a new alert"""
        try:
            alert_data['id'] = str(uuid.uuid4())
            alert_data['created_at'] = datetime.now()
            
            query = """
            INSERT INTO alert (id, wallet_id, blockchain_symbol, type, condition, threshold, status, created_at, notification_topic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Use connection from Database to execute
            self.db.get_connection().execute(query, [
                alert_data['id'],
                alert_data['wallet_id'],
                alert_data['blockchain_symbol'],
                alert_data['type'],
                alert_data['condition'],
                alert_data.get('threshold'),
                alert_data.get('status', 'active'),
                alert_data['created_at'],
                alert_data.get('notification_topic')
            ])
        except Exception as e:
            st.error(f"Failed to insert alert: {str(e)}")
            raise

    def get_all(self) -> List[tuple]:
        result = self.db.get_connection().execute("""
            SELECT 
                a.id, a.wallet_id, a.type, a.condition, a.threshold,
                a.status, a.created_at, a.last_triggered,
                w.address, w.blockchain_symbol, w.name as wallet_name
            FROM alert a
            JOIN wallet w ON a.wallet_id = w.id
            ORDER BY a.created_at DESC
        """).fetchall()
        # Return raw rows for index-based consumption in views
        return result
    
    def get_by_wallet(self, wallet_id: str) -> List[Dict[str, Any]]:
        result = self.db.get_connection().execute("""
            SELECT 
                a.id, a.wallet_id, a.type, a.condition, a.threshold,
                a.status, a.created_at, a.last_triggered,
                w.address, w.blockchain_symbol, w.name as wallet_name
            FROM alert a
            JOIN wallet w ON a.wallet_id = w.id
            WHERE a.wallet_id = ?
            ORDER BY a.created_at DESC
        """, [wallet_id]).fetchall()
        return [dict(row) for row in result]
    
    def update_status(self, alert_id: str, status: str) -> None:
        self.db.get_connection().execute("""
            UPDATE alert
            SET status = ?, last_triggered = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [status, alert_id])

    def delete(self, alert_id: str) -> None:
        """Delete an alert by ID"""
        self.db.get_connection().execute(
            "DELETE FROM alert WHERE id = ?", [alert_id]
        )

class Workflow:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, workflow_data: Dict[str, Any]) -> None:
        query = """
        INSERT INTO workflow (id, name, description, trigger_type, trigger_condition,
                            action_type, action_params, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db.get_connection().execute(query, [
            uuid.uuid4(),  # UUID type, not string
            workflow_data['name'],
            workflow_data.get('description'),
            workflow_data['trigger_type'],
            workflow_data['trigger_condition'],
            workflow_data['action_type'],
            workflow_data.get('action_params', {}),
            workflow_data.get('status', 'active')
        ])

    def get_all(self) -> List[Dict[str, Any]]:
        # Return raw rows for workflow list
        return self.db.get_connection().execute("""
            SELECT * FROM workflow
            ORDER BY created_at DESC
        """).fetchall()
    
    def get_active(self) -> List[Dict[str, Any]]:
        # Return raw rows for active workflows
        return self.db.get_connection().execute("""
            SELECT * FROM workflow
            WHERE status = 'active'
            ORDER BY created_at DESC
        """).fetchall()
    
    def update_status(self, workflow_id: str, status: str) -> None:
        self.db.get_connection().execute("""
            UPDATE workflow
            SET status = ?, last_run = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [status, workflow_id])

class Agent:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, agent_data: Dict[str, Any]) -> None:
        query = """
        INSERT INTO agent (id, name, type, config, max_budget, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        self.db.get_connection().execute(query, [
            uuid.uuid4(),  # UUID type, not string
            agent_data['name'],
            agent_data['type'],
            agent_data.get('config', {}),
            agent_data.get('max_budget', 0),
            agent_data.get('status', 'active')
        ])

    def get_all(self) -> List[Dict[str, Any]]:
        # Return raw rows for active agents
        return self.db.get_connection().execute(
            "SELECT * FROM agent WHERE status = 'active' ORDER BY created_at DESC"
        ).fetchall()
    
    def get_active(self) -> List[Dict[str, Any]]:
        # Return raw rows for active agents
        return self.db.get_connection().execute(
            "SELECT * FROM agent WHERE status = 'active' ORDER BY created_at DESC"
        ).fetchall()
    
    def update_status(self, agent_id: str, status: str) -> None:
        self.db.get_connection().execute("""
            UPDATE agent
            SET status = ?, last_active = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [status, agent_id])

class NotificationService:
    """Model for storing notification endpoints"""
    def __init__(self, db: Database):
        self.conn = db.get_connection()

    def get_all(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute("SELECT id, type, url FROM notification_service").fetchall()
        # Map each row tuple (id, type, url) to a dict
        return [
            {"id": r[0], "type": r[1], "url": r[2]}
            for r in rows
        ]

    def add(self, type: str, url: str) -> None:
        self.conn.execute(
            "INSERT INTO notification_service(id, type, url) VALUES (?, ?, ?)",
            [uuid.uuid4(), type, url],
        )

    def delete_all(self) -> None:
        self.conn.execute("DELETE FROM notification_service")

@st.cache_resource
def get_redis_connection(host: str | None = None, port: int = 6379, db: int = 0):
    """Return a Redis client, prioritising the REDIS_URL env variable.
    
    The connection order is:
    1. If REDIS_URL is set, use ``redis.from_url`` to respect the full URL (scheme, auth, db).
    2. Otherwise fall back to the supplied ``host``, ``port`` and ``db`` parameters (defaulting to ``localhost:6379/0``).
    """
    redis_url = os.getenv("REDIS_URL")
    try:
        if redis_url:
            # Use the provided URL (e.g. redis://user:pass@valkey:6379/1)
            client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=5,
                retry_on_timeout=True,
                max_connections=10,
            )
        else:
            client = redis.Redis(
                host=host or "localhost",
                port=port,
                db=db,
                decode_responses=True,
                socket_timeout=5,
                retry_on_timeout=True,
                max_connections=10,
            )

        # Quick connectivity test
        client.ping()
        return client
    except redis.ConnectionError as e:
        st.error(f"Could not connect to Redis: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error connecting to Redis: {str(e)}")
        return None

class Cache:
    _instance: Optional['Cache'] = None
    _settings: Optional[Settings] = None
    
    def __new__(cls) -> 'Cache':
        if cls._instance is None:
            cls._instance = super(Cache, cls).__new__(cls)
            cls._settings = Settings()
            cls._instance._init_cache()
        return cls._instance
    
    def _init_cache(self) -> None:
        """Initialize Redis cache connection"""
        # Determine Redis connection details from environment or settings
        redis_url = os.getenv('REDIS_URL') or Cache._settings.redis.get('url', 'redis://localhost:6379')
        parsed = urlparse(redis_url)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 6379
        try:
            db = int(parsed.path.lstrip('/')) if parsed.path.strip('/') else Cache._settings.redis.get('db', 0)
        except ValueError:
            db = 0

        self.redis = get_redis_connection(host=host, port=port, db=db)

        logger = logging.getLogger("cache")
        if self.redis:
            logger.info("Connected to Redis at %s:%s [db %s]", host, port, db)
        else:
            logger.error("Failed to connect to Redis at %s:%s [db %s]", host, port, db)
        
        # Only enable caching if configured
        self.enabled = self._settings.cache.get('enabled', False)
        self.ttl = self._settings.cache.get('ttl', 300)  # Default 5 minutes
    
    def is_connected(self):
        """Check if Redis connection is active"""
        try:
            connected = bool(self.redis and self.redis.ping())
            if not connected:
                logging.getLogger("cache").warning("Redis ping failed – cache disabled")
            return connected
        except Exception as e:
            logging.getLogger("cache").error("Error checking Redis connection: %s", e)
            st.error(f"Error checking Redis connection: {str(e)}")
            return False

    def cache_alert(self, alert_data):
        """Cache alert data in Redis using format alert:blockchain_symbol:wallet_id"""
        logger = logging.getLogger("cache")
        if not self.is_connected():
            logger.warning("Cannot cache alert %s – Redis not connected", alert_data.get('id'))
            return False

        try:
            key = f"alert:{alert_data['blockchain_symbol'].lower()}:{alert_data['wallet_id']}"
            
            # Redis requires string/number/bytes values. Convert unsupported types.
            def _serialize_val(v):
                from datetime import datetime as _dt
                import uuid as _uuid
                if v is None:
                    return ""
                if isinstance(v, (str, int, float)):
                    return v
                if isinstance(v, bool):
                    return int(v)  # store as 0/1
                if isinstance(v, (_uuid.UUID, _dt)):
                    return str(v)
                # Fallback to str for other objects
                return str(v)

            safe_mapping = {k: _serialize_val(v) for k, v in alert_data.items()}
            res = self.redis.hset(key, mapping=safe_mapping)
            if getattr(self, 'ttl', None):
                self.redis.expire(key, self.ttl)
            logger.debug("Cached alert %s to %s (result=%s)", alert_data.get('id'), key, res)
            return res
        except Exception as e:
            logger.error("Error caching alert %s: %s", alert_data.get('id'), e)
            st.error(f"Error caching alert: {str(e)}")
            return False

    def get_cached_data(self, key):
        """Get cached data by key"""
        logger = logging.getLogger("cache")
        if not self.is_connected():
            logger.debug("get_cached_data: Redis not connected for key %s", key)
            return None
        try:
            # Try hash get first
            data = self.redis.hgetall(key)
            if data:
                logger.debug("Retrieved hash data for %s: %s", key, data)
                return data
            # If not a hash, try string get
            val = self.redis.get(key)
            logger.debug("Retrieved string data for %s: %s", key, val)
            return val
        except Exception as e:
            logger.error("Error getting cached data for %s: %s", key, e)
            st.error(f"Error getting cached data: {str(e)}")
            return None

    def cache_wallet(self, wallet_data):
        """Cache wallet data in Redis"""
        if not self.is_connected():
            return False
            
        try:
            key = f"{wallet_data['blockchain_symbol']}:name:{wallet_data['address']}".lower()
            return self.redis.set(key, wallet_data['name'] or wallet_data['address'])
        except Exception as e:
            st.error(f"Error caching wallet: {str(e)}")
            return False

    def cache_workflow(self, workflow_data):
        """Cache workflow data in Redis"""
        if not self.is_connected():
            return False
            
        try:
            key = f"workflows:{workflow_data['id']}".lower()
            return self.redis.hset(key, mapping=workflow_data)
        except Exception as e:
            st.error(f"Error caching workflow: {str(e)}")
            return False

    def cache_agent(self, agent_data):
        """Cache agent data in Redis"""
        if not self.is_connected():
            return False
            
        try:
            key = f"agents:{agent_data['id']}".lower()
            return self.redis.hset(key, mapping=agent_data)
        except Exception as e:
            st.error(f"Error caching agent: {str(e)}")
            return False

    def delete_alert(self, blockchain_symbol: str, wallet_id: str) -> bool:
        """Delete cached alert data in Redis"""
        if not self.is_connected():
            return False
        try:
            key = f"alert:{blockchain_symbol.lower()}:{wallet_id}"
            return bool(self.redis.delete(key))
        except Exception as e:
            st.error(f"Error deleting cached alert: {str(e)}")
            return False
