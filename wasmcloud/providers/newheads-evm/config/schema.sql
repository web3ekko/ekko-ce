-- Database schema for newheads EVM provider configuration
-- Supports admin API with audit trail and versioning for EVM chains only

-- Chain configurations table
CREATE TABLE chain_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id VARCHAR(100) UNIQUE NOT NULL,
    chain_name VARCHAR(200) NOT NULL,
    network VARCHAR(50) NOT NULL,           -- ethereum, polygon, bitcoin, etc.
    subnet VARCHAR(50) NOT NULL,            -- mainnet, goerli, testnet, etc.
    vm_type VARCHAR(20) NOT NULL DEFAULT 'evm',  -- Only 'evm' supported by this provider
    
    -- Connection details
    rpc_url TEXT NOT NULL,
    ws_url TEXT NOT NULL,
    network_id BIGINT,
    
    -- Status
    enabled BOOLEAN DEFAULT false,
    
    -- NATS subjects (auto-generated but stored for reference)
    newheads_subject VARCHAR(200) NOT NULL,
    config_input_subject VARCHAR(200) NOT NULL,
    status_output_subject VARCHAR(200) NOT NULL,
    control_input_subject VARCHAR(200) NOT NULL,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),                -- Admin user who created this
    updated_by VARCHAR(100),                -- Admin user who last updated this
    
    -- Additional configuration (JSON for flexibility)
    extra_config JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT valid_vm_type CHECK (vm_type = 'evm'),  -- This provider only supports EVM chains
    CONSTRAINT valid_network CHECK (network ~ '^[a-z0-9-]+$'),
    CONSTRAINT valid_subnet CHECK (subnet ~ '^[a-z0-9-]+$')
);

-- Configuration change audit log
CREATE TABLE config_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,            -- CREATE, UPDATE, DELETE, ENABLE, DISABLE
    
    -- Change details
    old_config JSONB,                       -- Previous configuration
    new_config JSONB,                       -- New configuration
    changes JSONB,                          -- Specific fields that changed
    
    -- Metadata
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    admin_user VARCHAR(100),                -- Admin who made the change
    admin_ip INET,                          -- IP address of admin
    reason TEXT,                            -- Optional reason for change
    
    -- Reference to current config
    FOREIGN KEY (chain_id) REFERENCES chain_configs(chain_id) ON DELETE CASCADE
);

-- Provider status tracking
CREATE TABLE provider_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id VARCHAR(100) NOT NULL,
    
    -- Connection status
    status VARCHAR(20) NOT NULL,            -- active, connecting, disconnected, error
    last_block_received BIGINT,
    total_blocks_received BIGINT DEFAULT 0,
    connection_errors BIGINT DEFAULT 0,
    
    -- Timestamps
    connected_at TIMESTAMPTZ,
    last_block_at TIMESTAMPTZ,
    last_error_at TIMESTAMPTZ,
    last_error_message TEXT,
    
    -- Performance metrics
    avg_block_time_ms DECIMAL(10,2),
    blocks_per_minute DECIMAL(10,2),
    
    -- Updated timestamp
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (chain_id) REFERENCES chain_configs(chain_id) ON DELETE CASCADE,
    CONSTRAINT valid_status CHECK (status IN ('active', 'connecting', 'disconnected', 'error'))
);

-- Admin users table (for future admin API)
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,    -- bcrypt hash
    
    -- Permissions
    role VARCHAR(50) DEFAULT 'viewer',      -- admin, editor, viewer
    permissions JSONB DEFAULT '[]',         -- Specific permissions array
    
    -- Status
    active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_role CHECK (role IN ('admin', 'editor', 'viewer'))
);

-- API keys for programmatic access
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,         -- Hash of the actual API key
    
    -- Permissions
    permissions JSONB DEFAULT '[]',         -- Array of allowed operations
    allowed_chains JSONB DEFAULT '[]',      -- Array of chain_ids this key can access
    
    -- Rate limiting
    rate_limit_per_minute INTEGER DEFAULT 60,
    
    -- Status
    active BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),                -- Admin who created this key
    
    UNIQUE(key_hash)
);

-- Indexes for performance
CREATE INDEX idx_chain_configs_chain_id ON chain_configs(chain_id);
CREATE INDEX idx_chain_configs_enabled ON chain_configs(enabled);
CREATE INDEX idx_chain_configs_network ON chain_configs(network);
CREATE INDEX idx_chain_configs_evm_type ON chain_configs(evm_type);

CREATE INDEX idx_audit_log_chain_id ON config_audit_log(chain_id);
CREATE INDEX idx_audit_log_timestamp ON config_audit_log(timestamp);
CREATE INDEX idx_audit_log_admin_user ON config_audit_log(admin_user);

CREATE INDEX idx_provider_status_chain_id ON provider_status(chain_id);
CREATE INDEX idx_provider_status_status ON provider_status(status);
CREATE INDEX idx_provider_status_updated_at ON provider_status(updated_at);

CREATE INDEX idx_admin_users_username ON admin_users(username);
CREATE INDEX idx_admin_users_active ON admin_users(active);

CREATE INDEX idx_api_keys_active ON api_keys(active);
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at);

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic timestamp updates
CREATE TRIGGER update_chain_configs_updated_at 
    BEFORE UPDATE ON chain_configs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_users_updated_at 
    BEFORE UPDATE ON admin_users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Sample data for development
INSERT INTO chain_configs (
    chain_id, chain_name, network, subnet, evm_type,
    rpc_url, ws_url, network_id, enabled,
    newheads_subject, config_input_subject, status_output_subject, control_input_subject,
    created_by
) VALUES 
(
    'ethereum-mainnet',
    'Ethereum Mainnet',
    'ethereum',
    'mainnet', 
    'evm',
    'https://mainnet.infura.io/v3/YOUR_PROJECT_ID',
    'wss://mainnet.infura.io/ws/v3/YOUR_PROJECT_ID',
    1,
    false,
    'newheads.ethereum.mainnet.evm',
    'config.ethereum-mainnet.input',
    'status.ethereum-mainnet.output',
    'control.ethereum-mainnet.input',
    'system'
),
(
    'polygon-mainnet',
    'Polygon Mainnet',
    'polygon',
    'mainnet',
    'evm', 
    'https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID',
    'wss://polygon-mainnet.infura.io/ws/v3/YOUR_PROJECT_ID',
    137,
    false,
    'newheads.polygon.mainnet.evm',
    'config.polygon-mainnet.input',
    'status.polygon-mainnet.output',
    'control.polygon-mainnet.input',
    'system'
);

-- Sample admin user (password: 'admin123' - change in production!)
INSERT INTO admin_users (username, email, password_hash, role, created_by) VALUES 
('admin', 'admin@ekko.zone', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBdXwtO8S8VWO6', 'admin', 'system');

-- Views for easier querying
CREATE VIEW active_chains AS
SELECT 
    chain_id,
    chain_name,
    network,
    subnet,
    evm_type,
    newheads_subject,
    enabled,
    created_at,
    updated_at
FROM chain_configs 
WHERE enabled = true;

CREATE VIEW chain_status_summary AS
SELECT 
    cc.chain_id,
    cc.chain_name,
    cc.network,
    cc.subnet,
    cc.enabled,
    ps.status,
    ps.last_block_received,
    ps.total_blocks_received,
    ps.connection_errors,
    ps.last_block_at,
    ps.updated_at as status_updated_at
FROM chain_configs cc
LEFT JOIN provider_status ps ON cc.chain_id = ps.chain_id;
