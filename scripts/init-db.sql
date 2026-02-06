-- Ekko Cluster Database Initialization Script
-- This script runs when PostgreSQL container starts for the first time

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Set default timezone
SET timezone = 'UTC';

-- Create DuckLake catalog database
-- DuckLake manages its own metadata catalog automatically
-- We only need to create the database and grant permissions
SELECT 'CREATE DATABASE ducklake_catalog'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ducklake_catalog')\gexec

-- Grant all privileges to ekko user for DuckLake catalog
GRANT ALL PRIVILEGES ON DATABASE ducklake_catalog TO ekko;

-- Create database if not exists (handled by POSTGRES_DB env var)
-- Just adding this comment for clarity

-- Grant all privileges to the ekko user
-- Note: The database and user are created by PostgreSQL Docker image
-- based on POSTGRES_DB, POSTGRES_USER, and POSTGRES_PASSWORD env vars

-- Optional: Create additional schemas or initial data
-- Example:
-- CREATE SCHEMA IF NOT EXISTS ekko_analytics;
-- GRANT ALL ON SCHEMA ekko_analytics TO ekko;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Ekko database initialized successfully at %', NOW();
END
$$;