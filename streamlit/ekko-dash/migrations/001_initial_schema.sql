-- Initial schema migration

-- Blockchain table
CREATE TABLE IF NOT EXISTS blockchain (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL UNIQUE,
    chain_type VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Wallet table
CREATE TABLE IF NOT EXISTS wallet (
    id VARCHAR PRIMARY KEY,
    blockchain_symbol VARCHAR NOT NULL,
    address VARCHAR NOT NULL,
    name VARCHAR,
    balance DECIMAL(24,8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP,
    FOREIGN KEY (blockchain_symbol) REFERENCES blockchain(symbol),
    UNIQUE(blockchain_symbol, address)
);

-- Alert table
CREATE TABLE IF NOT EXISTS alert (
    id VARCHAR PRIMARY KEY,
    wallet_id VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    condition VARCHAR NOT NULL,
    threshold DECIMAL(24,8),
    status VARCHAR DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_triggered TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES wallet(id)
);

-- Workflow table
CREATE TABLE IF NOT EXISTS workflow (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    status VARCHAR DEFAULT 'active',
    trigger_type VARCHAR NOT NULL,
    trigger_condition TEXT,
    action_type VARCHAR NOT NULL,
    action_params TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_run TIMESTAMP
);

-- Agent table
CREATE TABLE IF NOT EXISTS agent (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'inactive',
    configuration TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);

-- Settings table
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
