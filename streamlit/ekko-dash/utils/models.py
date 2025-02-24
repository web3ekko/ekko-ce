import duckdb
import uuid
from datetime import datetime
import redis
import streamlit as st

class Database:
    def __init__(self):
        self.con = duckdb.connect("ekko.db")
        self.create_tables()
        self.populate_blockchain_table()

    def create_tables(self):
        self.create_blockchain_table()
        self.create_wallet_table()
        self.create_alert_table()
        self.create_workflow_table()
        self.create_agent_table()

    def populate_blockchain_table(self):
        # Check if the table is empty
        count_query = "SELECT COUNT(*) FROM blockchain"
        count_result = self.con.execute(count_query).fetchone()[0]
        
        if count_result == 0:
            # Insert default blockchains
            insert_query = """
            INSERT INTO blockchain (id, name, symbol, chain_type) VALUES
            (?, 'Ethereum', 'ETH', 'EVM'),
            (?, 'Avalanche', 'AVAX', 'EVM'),
            (?, 'Polygon', 'MATIC', 'EVM'),
            (?, 'Bitcoin', 'BTC', 'UTXO')
            """
            self.con.execute(insert_query, (
                uuid.uuid4(),
                uuid.uuid4(),
                uuid.uuid4(),
                uuid.uuid4()
            ))

    def create_blockchain_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS blockchain (
            id UUID PRIMARY KEY,
            name VARCHAR,
            symbol VARCHAR UNIQUE,
            chain_type VARCHAR
        )
        """
        self.con.execute(query)

    def create_wallet_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS wallet (
            id UUID PRIMARY KEY,
            blockchain_symbol VARCHAR,
            address VARCHAR,
            name VARCHAR,
            balance DECIMAL(24,8),
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            UNIQUE (blockchain_symbol, address)
        )
        """
        self.con.execute(query)

    def create_alert_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS alert (
            id UUID PRIMARY KEY,
            type VARCHAR,
            message TEXT,
            time VARCHAR,
            status VARCHAR,
            icon VARCHAR,
            priority VARCHAR,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """
        self.con.execute(query)

    def create_workflow_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS workflow (
            id UUID PRIMARY KEY,
            name VARCHAR,
            description TEXT,
            schedule VARCHAR,
            risk_level VARCHAR,
            status VARCHAR,
            last_run TIMESTAMP,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """
        self.con.execute(query)

    def create_agent_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS agent (
            id UUID PRIMARY KEY,
            name VARCHAR,
            agent_type VARCHAR,
            description TEXT,
            status VARCHAR,
            max_budget DECIMAL(24,8),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """
        self.con.execute(query)

class Blockchain:
    def __init__(self, db):
        self.db = db

    def insert(self, blockchain_data):
        query = """
        INSERT INTO blockchain (id, name, symbol, chain_type)
        VALUES (?, ?, ?, ?)
        """
        self.db.con.execute(query, (
            uuid.uuid4(),
            blockchain_data['name'],
            blockchain_data['symbol'],
            blockchain_data.get('chain_type')
        ))

    def get_all(self):
        return self.db.con.execute("SELECT * FROM blockchain").fetchall()
    
    def populate_blockchain_table(self):
        # Check if the table is empty
        count_query = "SELECT COUNT(*) FROM blockchain"
        count_result = self.con.execute(count_query).fetchone()[0]
        
        if count_result == 0:
            # Insert default blockchains
            insert_query = """
            INSERT INTO blockchain (id, name, symbol, chain_type) VALUES
            (?, 'Ethereum', 'ETH', 'EVM'),
            (?, 'Avalanche', 'AVAX', 'EVM'),
            (?, 'Polygon', 'MATIC', 'EVM'),
            (?, 'Bitcoin', 'BTC', 'UTXO')
            """
            self.con.execute(insert_query, (
                uuid.uuid4(),
                uuid.uuid4(),
                uuid.uuid4(),
                uuid.uuid4()
            ))

class Wallet:
    def __init__(self, db):
        self.db = db

    def insert(self, wallet_data):
        query = """
        INSERT INTO wallet (
            id, blockchain_symbol, address, name, balance, 
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.db.con.execute(query, (
            uuid.uuid4(),
            wallet_data['blockchain_symbol'],
            wallet_data['address'].lower(),  # Store addresses in lowercase
            wallet_data.get('name'),
            wallet_data.get('balance', 0),
            datetime.now(),
            datetime.now()
        ))

    def get_all(self):
        return self.db.con.execute("""
            SELECT w.*, b.name as blockchain_name 
            FROM wallet w 
            JOIN blockchain b ON w.blockchain_symbol = b.symbol
            ORDER BY w.created_at DESC
        """).fetchall()
    
    def get_by_blockchain(self, blockchain_symbol):
        query = """
            SELECT w.*, b.name as blockchain_name 
            FROM wallet w 
            JOIN blockchain b ON w.blockchain_symbol = b.symbol
            WHERE w.blockchain_symbol = ?
            ORDER BY w.created_at DESC
        """
        return self.db.con.execute(query, (blockchain_symbol,)).fetchall()
    
    def get_by_address(self, blockchain_symbol, address):
        query = """
            SELECT w.*, b.name as blockchain_name 
            FROM wallet w 
            JOIN blockchain b ON w.blockchain_symbol = b.symbol
            WHERE w.blockchain_symbol = ? AND w.address = ?
        """
        return self.db.con.execute(query, (blockchain_symbol, address.lower())).fetchone()
    
    def update_balance(self, blockchain_symbol, address, new_balance):
        query = """
            UPDATE wallet 
            SET balance = ?, updated_at = ?
            WHERE blockchain_symbol = ? AND address = ?
        """
        self.db.con.execute(query, (
            new_balance,
            datetime.now(),
            blockchain_symbol,
            address.lower()
        ))

class Alert:
    def __init__(self, db):
        self.db = db

    def insert(self, alert_data):
        query = """
        INSERT INTO alert (
            id, type, message, time, status, icon, 
            priority, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db.con.execute(query, (
            uuid.uuid4(),
            alert_data['type'],
            alert_data['message'],
            alert_data['time'],
            alert_data['status'],
            alert_data['icon'],
            alert_data['priority'],
            datetime.now(),
            datetime.now()
        ))

    def get_all(self):
        return self.db.con.execute("SELECT * FROM alert ORDER BY created_at DESC").fetchall()

class Workflow:
    def __init__(self, db):
        self.db = db

    def insert(self, workflow_data):
        query = """
        INSERT INTO workflow (
            id, name, description, schedule, risk_level,
            status, last_run, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db.con.execute(query, (
            uuid.uuid4(),
            workflow_data['name'],
            workflow_data['description'],
            workflow_data['schedule'],
            workflow_data['risk_level'],
            workflow_data['status'],
            workflow_data.get('last_run'),
            datetime.now(),
            datetime.now()
        ))

    def get_all(self):
        return self.db.con.execute("SELECT * FROM workflow ORDER BY created_at DESC").fetchall()

class Agent:
    def __init__(self, db):
        self.db = db

    def insert(self, agent_data):
        query = """
        INSERT INTO agent (
            id, name, agent_type, description, status,
            max_budget, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db.con.execute(query, (
            uuid.uuid4(),
            agent_data['name'],
            agent_data['agent_type'],
            agent_data['description'],
            agent_data['status'],
            agent_data['max_budget'],
            datetime.now(),
            datetime.now()
        ))

    def get_all(self):
        return self.db.con.execute("SELECT * FROM agent ORDER BY created_at DESC").fetchall()

@st.cache_resource
def get_redis_connection(host="localhost", port=6379, db=0):
    """
    Creates or returns a cached Redis connection.
    
    Args:
        host (str): Redis host address
        port (int): Redis port number
        db (int): Redis database number
        
    Returns:
        redis.Redis: A Redis connection instance
    """
    try:
        client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,  # Automatically decode responses to strings
            socket_timeout=5,  # 5 second timeout
            retry_on_timeout=True,  # Retry once on timeout
            max_connections=10  # Connection pool size
        )
        # Test the connection
        client.ping()
        return client
    except redis.ConnectionError as e:
        st.error(f"Could not connect to Redis: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error connecting to Redis: {str(e)}")
        return None

class Cache:
    def __init__(self, host="localhost", port=6379, db=0):
        self.redis = get_redis_connection(host, port, db)
        if not self.redis:
            st.warning("Redis cache is not available. Some features may be slower.")
    
    def is_connected(self):
        """Check if Redis connection is active"""
        try:
            return bool(self.redis and self.redis.ping())
        except Exception as e:
            st.error(f"Error checking Redis connection: {str(e)}")
            return False

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

    def cache_alert(self, alert_data):
        """Cache alert data in Redis"""
        if not self.is_connected():
            return False
            
        try:
            key = f"alerts:{alert_data['id']}".lower()
            return self.redis.hset(key, mapping=alert_data)
        except Exception as e:
            st.error(f"Error caching alert: {str(e)}")
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

    def get_cached_data(self, key):
        """Get cached data by key"""
        if not self.is_connected():
            return None
            
        try:
            # Try hash get first
            data = self.redis.hgetall(key)
            if data:
                return data
            # If not a hash, try string get
            return self.redis.get(key)
        except Exception as e:
            st.error(f"Error getting cached data: {str(e)}")
            return None
