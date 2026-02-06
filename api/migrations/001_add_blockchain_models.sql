-- Migration: Add blockchain models from Django ekko app
-- This creates the database schema for the ported Django models

-- Blockchain table
CREATE TABLE IF NOT EXISTS blockchain (
    id UUID DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE,
    symbol VARCHAR(255) PRIMARY KEY,
    chain_type VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- DAO table
CREATE TABLE IF NOT EXISTS dao (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    recommended BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Wallet table (extended with ekko-ce fields)
CREATE TABLE IF NOT EXISTS wallet (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blockchain_symbol VARCHAR(255) NOT NULL REFERENCES blockchain(symbol),
    address VARCHAR(255) NOT NULL,
    name TEXT NOT NULL,
    derived_name VARCHAR(255),
    domains JSONB,
    recommended BOOLEAN DEFAULT FALSE NOT NULL,
    -- Extended fields from ekko-ce integration
    balance VARCHAR(255),  -- Current balance as string to handle large numbers
    status VARCHAR(50) DEFAULT 'active' NOT NULL,  -- active, inactive, monitoring
    subnet VARCHAR(100) DEFAULT 'mainnet' NOT NULL,  -- mainnet, testnet, etc.
    description TEXT,  -- User description
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(blockchain_symbol, address)
);

-- Wallet subscription table
CREATE TABLE IF NOT EXISTS "walletSubscription" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID NOT NULL REFERENCES wallet(id) ON DELETE CASCADE,
    name VARCHAR(255),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    notifications_count INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(wallet_id, user_id)
);

-- DAO subscription table
CREATE TABLE IF NOT EXISTS "daoSubscription" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dao_id UUID NOT NULL REFERENCES dao(id) ON DELETE CASCADE,
    name VARCHAR(255),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    notifications_count INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(dao_id, user_id)
);

-- DAO-Wallet relationship table
CREATE TABLE IF NOT EXISTS "daoWallet" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dao_id UUID NOT NULL REFERENCES dao(id) ON DELETE CASCADE,
    wallet_id UUID NOT NULL REFERENCES wallet(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(dao_id, wallet_id)
);

-- Token table
CREATE TABLE IF NOT EXISTS token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blockchain_symbol VARCHAR(255) NOT NULL REFERENCES blockchain(symbol),
    name VARCHAR(255) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Images table
CREATE TABLE IF NOT EXISTS images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url VARCHAR(1024) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Story table
CREATE TABLE IF NOT EXISTS story (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255),
    description TEXT,
    content TEXT,
    publication_date TIMESTAMP WITH TIME ZONE,
    image_url VARCHAR(1024),
    url VARCHAR(1024),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Story-Blockchain relationship table
CREATE TABLE IF NOT EXISTS story_blockchain (
    story_id UUID NOT NULL REFERENCES story(id) ON DELETE CASCADE,
    blockchain_symbol VARCHAR(255) NOT NULL REFERENCES blockchain(symbol),
    PRIMARY KEY (story_id, blockchain_symbol)
);

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User settings table (extends existing user_profiles)
CREATE TABLE IF NOT EXISTS "userSettings" (
    user_id UUID PRIMARY KEY REFERENCES user_profiles(id) ON DELETE CASCADE,
    mute BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Wallet balance history table (from ekko-ce integration)
CREATE TABLE IF NOT EXISTS wallet_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id UUID NOT NULL REFERENCES wallet(id) ON DELETE CASCADE,
    balance VARCHAR(255) NOT NULL,  -- Balance as string to handle large numbers
    token_price VARCHAR(255),  -- Token price in USD
    fiat_value VARCHAR(255),  -- Fiat value in USD
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add extended fields to user_profiles table for ekko-ce compatibility
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'user' NOT NULL;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_wallet_blockchain ON wallet(blockchain_symbol);
CREATE INDEX IF NOT EXISTS idx_wallet_address ON wallet(address);
CREATE INDEX IF NOT EXISTS idx_wallet_recommended ON wallet(recommended);

CREATE INDEX IF NOT EXISTS idx_wallet_subscription_wallet ON "walletSubscription"(wallet_id);
CREATE INDEX IF NOT EXISTS idx_wallet_subscription_user ON "walletSubscription"(user_id);

CREATE INDEX IF NOT EXISTS idx_dao_subscription_dao ON "daoSubscription"(dao_id);
CREATE INDEX IF NOT EXISTS idx_dao_subscription_user ON "daoSubscription"(user_id);

CREATE INDEX IF NOT EXISTS idx_dao_wallet_dao ON "daoWallet"(dao_id);
CREATE INDEX IF NOT EXISTS idx_dao_wallet_wallet ON "daoWallet"(wallet_id);

CREATE INDEX IF NOT EXISTS idx_token_blockchain ON token(blockchain_symbol);
CREATE INDEX IF NOT EXISTS idx_token_symbol ON token(symbol);

-- Indexes for wallet balance history
CREATE INDEX IF NOT EXISTS idx_wallet_balance_wallet ON wallet_balances(wallet_id);
CREATE INDEX IF NOT EXISTS idx_wallet_balance_timestamp ON wallet_balances(timestamp);
CREATE INDEX IF NOT EXISTS idx_wallet_balance_wallet_timestamp ON wallet_balances(wallet_id, timestamp);

-- Insert some initial blockchain data
INSERT INTO blockchain (name, symbol, chain_type) VALUES
    ('Ethereum', 'eth', 'EVM'),
    ('Bitcoin', 'btc', 'UTXO'),
    ('Solana', 'sol', 'SVM'),
    ('Polygon', 'matic', 'EVM'),
    ('Avalanche', 'avax', 'EVM'),
    ('Binance Smart Chain', 'bnb', 'EVM')
ON CONFLICT (symbol) DO NOTHING;
