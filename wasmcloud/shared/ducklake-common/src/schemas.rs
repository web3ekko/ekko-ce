//! Arrow schemas for DuckLake tables
//!
//! Implements the USDT specification for blockchain data storage
//! with proper partitioning and optimization for query performance.

use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use std::sync::Arc;

/// Create Arrow schema for the blocks table
pub fn blocks_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns (first for optimization)
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        Field::new("shard", DataType::Int32, false),
        // Primary keys and identifiers
        Field::new("block_number", DataType::Int64, false),
        Field::new("block_hash", DataType::Utf8, false),
        Field::new("parent_hash", DataType::Utf8, true),
        Field::new(
            "block_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        // Block metadata
        Field::new("gas_limit", DataType::Int64, true),
        Field::new("gas_used", DataType::Int64, true),
        Field::new("difficulty", DataType::Int64, true),
        Field::new("total_difficulty", DataType::Int64, true),
        Field::new("size_bytes", DataType::Int64, true),
        Field::new("transaction_count", DataType::Int32, true),
        // Miner/validator info
        Field::new("miner", DataType::Utf8, true),
        Field::new("nonce", DataType::Utf8, true),
        Field::new("extra_data", DataType::Utf8, true),
        // Chain-specific fields
        Field::new("base_fee_per_gas", DataType::Int64, true), // EVM (EIP-1559)
        Field::new("withdrawal_root", DataType::Utf8, true),   // EVM (Shanghai)
        Field::new("slot_number", DataType::Int64, true),      // SVM (Solana)
        Field::new("validator_index", DataType::Int32, true),  // Cosmos
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the unified transactions table
///
/// This is the single source of truth for all blockchain transactions.
/// Supports EVM, SVM, and UTXO chains with type-specific fields.
/// Includes decoded function data from ABI decoder.
///
/// Partitioning: chain_id → year(block_timestamp) → month → day (function-based)
/// Z-order: from_address, to_address, block_number
pub fn transactions_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // ═══════════════════════════════════════════════════════════════════════════
        // PARTITION COLUMNS (function-based: chain_id → year → month → day)
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // NETWORK IDENTIFICATION
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("network", DataType::Utf8, false), // ethereum, polygon, solana, bitcoin
        Field::new("subnet", DataType::Utf8, false),  // mainnet, sepolia, devnet
        Field::new("vm_type", DataType::Utf8, false), // evm, svm, utxo
        // ═══════════════════════════════════════════════════════════════════════════
        // PRIMARY IDENTIFIERS
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("block_number", DataType::Int64, false),
        Field::new(
            "block_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new("transaction_hash", DataType::Utf8, false),
        Field::new("transaction_index", DataType::Int32, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // CORE TRANSACTION FIELDS
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("from_address", DataType::Utf8, true),
        Field::new("to_address", DataType::Utf8, true),
        Field::new("value", DataType::Decimal128(38, 18), true),
        Field::new("gas_limit", DataType::Int64, true),
        Field::new("gas_used", DataType::Int64, true),
        Field::new("gas_price", DataType::Decimal128(38, 18), true),
        Field::new("max_fee_per_gas", DataType::Decimal128(38, 18), true),
        Field::new(
            "max_priority_fee_per_gas",
            DataType::Decimal128(38, 18),
            true,
        ),
        // Transaction status and results
        Field::new("status", DataType::Utf8, false),
        Field::new("transaction_fee", DataType::Decimal128(38, 18), true),
        Field::new("effective_gas_price", DataType::Decimal128(38, 18), true),
        // Input data
        Field::new("input_data", DataType::Utf8, true),
        Field::new("method_signature", DataType::Utf8, true),
        // ═══════════════════════════════════════════════════════════════════════════
        // TRANSACTION CLASSIFICATION (from processed_transfers)
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("transaction_type", DataType::Utf8, false), // TRANSFER, CONTRACT_CALL, CONTRACT_CREATE
        Field::new("transaction_subtype", DataType::Utf8, true), // native, erc20, swap, stake, etc.
        // ═══════════════════════════════════════════════════════════════════════════
        // VALUE ENRICHMENT (from processed_transfers)
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("amount_native", DataType::Float64, true), // Amount in native units (e.g., ETH)
        Field::new("amount_usd", DataType::Float64, true),    // USD value at tx time
        Field::new("fee_usd", DataType::Float64, true),       // Fee in USD
        Field::new("transfer_category", DataType::Utf8, true), // Micro/Small/Medium/Large/Whale
        Field::new("sender_type", DataType::Utf8, true),      // EOA/Contract/Unknown
        Field::new("recipient_type", DataType::Utf8, true),   // EOA/Contract/Unknown
        // ═══════════════════════════════════════════════════════════════════════════
        // DECODED FUNCTION DATA (from abi-decoder actor)
        // Based on PRD-ABI-Decoder-Actor-USDT.md
        // ═══════════════════════════════════════════════════════════════════════════
        // Decoded function identification
        Field::new("decoded_function_name", DataType::Utf8, true), // e.g., "transfer", "swap", "approve"
        Field::new("decoded_function_signature", DataType::Utf8, true), // e.g., "transfer(address,uint256)"
        Field::new("decoded_function_selector", DataType::Utf8, true), // e.g., "0xa9059cbb" (first 4 bytes)
        // Decoded parameters (JSON array)
        // Format: [{"name":"_to","param_type":"address","value":"0x...","raw_value":"0x..."}]
        Field::new("decoded_parameters", DataType::Utf8, true), // JSON array of DecodedParameter
        // Decoding metadata
        Field::new("decoding_status", DataType::Utf8, true), // Success, AbiNotFound, InvalidInput, DecodingError, Timeout, NativeTransfer, ContractCreation
        Field::new("abi_source", DataType::Utf8, true), // etherscan, sourcify, 4byte, manual, unknown
        Field::new("decoding_time_ms", DataType::Int32, true), // Time taken to decode in milliseconds
        // Human-readable summary (optional, for UI display)
        Field::new("decoded_summary", DataType::Utf8, true), // e.g., "transfer 1.5 ETH to 0x742e..."
        // ═══════════════════════════════════════════════════════════════════════════
        // CHAIN-SPECIFIC FIELDS
        // ═══════════════════════════════════════════════════════════════════════════
        // EVM fields
        Field::new("nonce", DataType::Int64, true),
        Field::new("v", DataType::Int64, true),
        Field::new("r", DataType::Utf8, true),
        Field::new("s", DataType::Utf8, true),
        // SVM (Solana) fields
        Field::new("recent_blockhash", DataType::Utf8, true),
        Field::new("compute_units_consumed", DataType::Int64, true),
        // ═══════════════════════════════════════════════════════════════════════════
        // PROCESSING METADATA
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("processor_id", DataType::Utf8, true),
        Field::new("correlation_id", DataType::Utf8, true),
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new(
            "decoded_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            true,
        ),
    ]))
}

/// Create Arrow schema for the logs table (smart contract events)
///
/// Enhanced with decoded event data from ABI decoder.
/// Partitioning: chain_id → year(block_timestamp) → month → day
/// Z-order: address, topic0, block_number
pub fn logs_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // ═══════════════════════════════════════════════════════════════════════════
        // PARTITION COLUMNS (function-based)
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // PRIMARY IDENTIFIERS
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("block_number", DataType::Int64, false),
        Field::new(
            "block_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new("transaction_hash", DataType::Utf8, false),
        Field::new("log_index", DataType::Int32, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // LOG DATA
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("address", DataType::Utf8, false),
        Field::new("topic0", DataType::Utf8, true),
        Field::new("topic1", DataType::Utf8, true),
        Field::new("topic2", DataType::Utf8, true),
        Field::new("topic3", DataType::Utf8, true),
        Field::new("data", DataType::Utf8, true),
        // ═══════════════════════════════════════════════════════════════════════════
        // RAW EVENT CLASSIFICATION
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("event_name", DataType::Utf8, true),
        Field::new("event_signature", DataType::Utf8, true),
        // Standard events (optimization for common patterns)
        Field::new("is_transfer", DataType::Boolean, true),
        Field::new("is_approval", DataType::Boolean, true),
        Field::new("is_swap", DataType::Boolean, true),
        Field::new("is_mint", DataType::Boolean, true),
        Field::new("is_burn", DataType::Boolean, true),
        // ═══════════════════════════════════════════════════════════════════════════
        // DECODED EVENT DATA (from ABI decoder)
        // Based on PRD-ABI-Decoder-Actor-USDT.md - US-AD-002: Event Log Decoding
        // ═══════════════════════════════════════════════════════════════════════════
        // Decoded event identification
        Field::new("decoded_event_name", DataType::Utf8, true), // e.g., "Transfer", "Approval", "Swap"
        Field::new("decoded_event_signature", DataType::Utf8, true), // Full event signature
        // Decoded event parameters (JSON array)
        // Format: [{"name":"from","type":"address","indexed":true,"value":"0x..."}]
        Field::new("decoded_event_parameters", DataType::Utf8, true), // JSON array of decoded params
        // Decoding metadata
        Field::new("event_decoding_status", DataType::Utf8, true), // Success, AbiNotFound, Anonymous, Failed
        Field::new("is_anonymous_event", DataType::Boolean, true), // True if event has no signature topic
        // ═══════════════════════════════════════════════════════════════════════════
        // PROCESSING METADATA
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new(
            "decoded_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            true,
        ),
    ]))
}

/// Create Arrow schema for the token_prices table
pub fn token_prices_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        Field::new("shard", DataType::Int32, false),
        // Time and block context
        Field::new("block_number", DataType::Int64, false),
        Field::new(
            "price_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        // Token identification
        Field::new("token_address", DataType::Utf8, false),
        Field::new("token_symbol", DataType::Utf8, true),
        Field::new("token_name", DataType::Utf8, true),
        Field::new("token_decimals", DataType::Int32, true),
        // Price data
        Field::new("price_usd", DataType::Decimal128(18, 8), true),
        Field::new("price_eth", DataType::Decimal128(18, 8), true),
        Field::new("price_btc", DataType::Decimal128(18, 8), true),
        // Price source and metadata
        Field::new("source_type", DataType::Utf8, false),
        Field::new("source_name", DataType::Utf8, false),
        Field::new("source_address", DataType::Utf8, true),
        // DEX-specific data
        Field::new("dex_pool_address", DataType::Utf8, true),
        Field::new("liquidity_usd", DataType::Decimal128(18, 8), true),
        Field::new("volume_24h_usd", DataType::Decimal128(18, 8), true),
        // Oracle-specific data
        Field::new("round_id", DataType::Int64, true),
        Field::new("confidence_interval", DataType::Decimal128(8, 4), true),
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the protocol_events table
pub fn protocol_events_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        Field::new("shard", DataType::Int32, false),
        // Primary identifiers
        Field::new("block_number", DataType::Int64, false),
        Field::new("transaction_hash", DataType::Utf8, false),
        Field::new("log_index", DataType::Int32, true),
        // Protocol identification
        Field::new("protocol_name", DataType::Utf8, false),
        Field::new("protocol_version", DataType::Utf8, true),
        Field::new("contract_address", DataType::Utf8, false),
        // Event classification
        Field::new("event_category", DataType::Utf8, false),
        Field::new("event_name", DataType::Utf8, false),
        // User and amounts
        Field::new("user_address", DataType::Utf8, true),
        Field::new("token_in_address", DataType::Utf8, true),
        Field::new("token_in_symbol", DataType::Utf8, true),
        Field::new("amount_in", DataType::Decimal128(38, 18), true),
        Field::new("token_out_address", DataType::Utf8, true),
        Field::new("token_out_symbol", DataType::Utf8, true),
        Field::new("amount_out", DataType::Decimal128(38, 18), true),
        // Protocol-specific data
        Field::new("pool_address", DataType::Utf8, true),
        Field::new("position_id", DataType::Int64, true),
        Field::new("fee_tier", DataType::Int32, true),
        Field::new("tick_lower", DataType::Int32, true),
        Field::new("tick_upper", DataType::Int32, true),
        // Economic data
        Field::new("value_usd", DataType::Decimal128(18, 8), true),
        Field::new("fees_usd", DataType::Decimal128(18, 8), true),
        Field::new("gas_cost_usd", DataType::Decimal128(18, 8), true),
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new(
            "decoded_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            true,
        ),
    ]))
}

/// Create Arrow schema for the contract_calls table
pub fn contract_calls_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        Field::new("shard", DataType::Int32, false),
        // Primary identifiers
        Field::new("block_number", DataType::Int64, false),
        Field::new(
            "block_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new("transaction_hash", DataType::Utf8, false),
        Field::new("call_index", DataType::Int32, false),
        // Call identification
        Field::new("from_address", DataType::Utf8, false),
        Field::new("to_address", DataType::Utf8, false),
        Field::new("call_type", DataType::Utf8, false),
        // Method information
        Field::new("method_signature", DataType::Utf8, true),
        Field::new("method_name", DataType::Utf8, true),
        Field::new("function_signature", DataType::Utf8, true),
        // Input and output data
        Field::new("input_data", DataType::Utf8, true),
        Field::new("output_data", DataType::Utf8, true),
        Field::new("decoded_input", DataType::Utf8, true),
        Field::new("decoded_output", DataType::Utf8, true),
        // Call context
        Field::new("gas_limit", DataType::Int64, true),
        Field::new("gas_used", DataType::Int64, true),
        Field::new("value", DataType::Decimal128(38, 18), true),
        Field::new("call_depth", DataType::Int32, true),
        // Call status
        Field::new("success", DataType::Boolean, false),
        Field::new("revert_reason", DataType::Utf8, true),
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new(
            "decoded_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            true,
        ),
    ]))
}

// =============================================================================
// DeFi Analytics Tables (NEW - Performance Optimization)
// =============================================================================

/// Create Arrow schema for the processed_transfers table
///
/// Stores processed/enriched transfer transactions from eth_transfers_processor.
/// Contains derived fields like amount_eth, transfer_category, sender_type.
/// Partitioning: chain_id → block_date → shard
/// Z-order: from_address, to_address, block_number
pub fn processed_transfers_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        Field::new("shard", DataType::Int32, false),
        // Network identification
        Field::new("network", DataType::Utf8, false),
        Field::new("subnet", DataType::Utf8, false),
        Field::new("vm_type", DataType::Utf8, false),
        // Transaction identification
        Field::new("transaction_hash", DataType::Utf8, false),
        Field::new("block_number", DataType::Int64, false),
        Field::new(
            "block_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        // Transfer addresses
        Field::new("from_address", DataType::Utf8, false),
        Field::new("to_address", DataType::Utf8, true),
        // Amount fields
        Field::new("amount_wei", DataType::Utf8, false), // Stored as string for precision
        Field::new("amount_eth", DataType::Float64, false),
        Field::new("amount_usd", DataType::Float64, true),
        // Gas and fees
        Field::new("gas_used", DataType::Int64, false),
        Field::new("gas_price", DataType::Utf8, false),
        Field::new("transaction_fee_wei", DataType::Utf8, false),
        Field::new("transaction_fee_eth", DataType::Float64, false),
        // Enrichment categories
        Field::new("transfer_category", DataType::Utf8, false), // Micro, Small, Medium, Large, Whale
        Field::new("sender_type", DataType::Utf8, false),       // EOA, Contract, Unknown
        Field::new("recipient_type", DataType::Utf8, false),    // EOA, Contract, Unknown
        // Balance context (optional)
        Field::new("sender_balance_before", DataType::Utf8, true),
        Field::new("sender_balance_after", DataType::Utf8, true),
        Field::new("recipient_balance_before", DataType::Utf8, true),
        Field::new("recipient_balance_after", DataType::Utf8, true),
        // Standardized enrichment fields
        Field::new("transaction_type", DataType::Utf8, false), // "transfer"
        Field::new("transaction_currency", DataType::Utf8, false), // "ETH", "USDT", etc.
        Field::new("transaction_value", DataType::Utf8, false), // "1.5 ETH"
        Field::new("transaction_subtype", DataType::Utf8, false), // "native", "erc20", "internal"
        Field::new("protocol", DataType::Utf8, true),          // None or "ERC20"
        Field::new("category", DataType::Utf8, false),         // "value_transfer"
        Field::new("decoded", DataType::Utf8, true),           // JSON blob with transfer details
        // Metadata
        Field::new("correlation_id", DataType::Utf8, false),
        Field::new("processor_id", DataType::Utf8, false),
        Field::new(
            "processed_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the wallet_activity table
///
/// Address-centric view for fast wallet tracking queries.
/// Partitioning: chain_id → address_prefix (first 4 hex chars) → block_date
/// Z-order: wallet_address, block_number, token_address
pub fn wallet_activity_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns (address-prefix partitioning)
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("address_prefix", DataType::Utf8, false), // First 4 hex chars after 0x
        Field::new("block_date", DataType::Date32, false),
        Field::new("shard", DataType::Int32, false),
        // Primary identifiers
        Field::new("wallet_address", DataType::Utf8, false),
        Field::new("counterparty_address", DataType::Utf8, true),
        Field::new("direction", DataType::Utf8, false), // "in" or "out"
        // Token information
        Field::new("token_address", DataType::Utf8, true), // null for native
        Field::new("token_symbol", DataType::Utf8, true),
        Field::new("amount", DataType::Decimal128(38, 18), false),
        Field::new("amount_usd", DataType::Decimal128(18, 8), true),
        // Transaction context
        Field::new("block_number", DataType::Int64, false),
        Field::new("transaction_hash", DataType::Utf8, false),
        Field::new("log_index", DataType::Int32, true),
        Field::new("activity_type", DataType::Utf8, false), // transfer, swap, stake, etc.
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the lp_positions table
///
/// Tracks LP positions, yields, and impermanent loss for DeFi protocols.
/// Partitioning: chain_id → block_date → shard
/// Z-order: user_address, pool_address, block_number
pub fn lp_positions_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        Field::new("shard", DataType::Int32, false),
        // User and protocol
        Field::new("user_address", DataType::Utf8, false),
        Field::new("protocol_name", DataType::Utf8, false), // uniswap_v3, curve, etc.
        Field::new("pool_address", DataType::Utf8, false),
        Field::new("position_id", DataType::Utf8, true), // NFT ID for Uni v3
        // Token pair
        Field::new("token0_address", DataType::Utf8, false),
        Field::new("token0_symbol", DataType::Utf8, true),
        Field::new("token1_address", DataType::Utf8, false),
        Field::new("token1_symbol", DataType::Utf8, true),
        // Position details
        Field::new("liquidity", DataType::Decimal128(38, 18), false),
        Field::new("amount0", DataType::Decimal128(38, 18), true),
        Field::new("amount1", DataType::Decimal128(38, 18), true),
        Field::new("tick_lower", DataType::Int32, true), // Uni v3 concentrated
        Field::new("tick_upper", DataType::Int32, true),
        // Fees and value
        Field::new("fees_earned_token0", DataType::Decimal128(38, 18), true),
        Field::new("fees_earned_token1", DataType::Decimal128(38, 18), true),
        Field::new("fees_earned_usd", DataType::Decimal128(18, 8), true),
        Field::new("position_value_usd", DataType::Decimal128(18, 8), true),
        // Action tracking
        Field::new("action", DataType::Utf8, false), // mint, burn, collect, increase, decrease
        Field::new("block_number", DataType::Int64, false),
        Field::new("transaction_hash", DataType::Utf8, false),
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the yield_events table
///
/// Tracks yield farming rewards, staking, and harvests.
/// Partitioning: chain_id → block_date → shard
/// Z-order: user_address, protocol_name, block_number
pub fn yield_events_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        Field::new("shard", DataType::Int32, false),
        // User and protocol
        Field::new("user_address", DataType::Utf8, false),
        Field::new("protocol_name", DataType::Utf8, false), // aave, compound, yearn
        Field::new("vault_address", DataType::Utf8, false),
        Field::new("underlying_token", DataType::Utf8, true),
        // Action and amounts
        Field::new("action", DataType::Utf8, false), // deposit, withdraw, stake, unstake, harvest, claim
        Field::new("amount", DataType::Decimal128(38, 18), false),
        Field::new("amount_usd", DataType::Decimal128(18, 8), true),
        // Rewards
        Field::new("reward_token", DataType::Utf8, true),
        Field::new("reward_amount", DataType::Decimal128(38, 18), true),
        Field::new("reward_usd", DataType::Decimal128(18, 8), true),
        Field::new("apy_at_time", DataType::Decimal128(8, 4), true), // APY when action occurred
        // Transaction context
        Field::new("block_number", DataType::Int64, false),
        Field::new("transaction_hash", DataType::Utf8, false),
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the token_holdings table
///
/// Point-in-time balance snapshots for portfolio analytics.
/// Partitioning: chain_id → snapshot_date → shard
/// Z-order: wallet_address, token_address, block_number
pub fn token_holdings_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("snapshot_date", DataType::Date32, false), // Daily snapshots
        Field::new("shard", DataType::Int32, false),
        // Wallet and token
        Field::new("wallet_address", DataType::Utf8, false),
        Field::new("token_address", DataType::Utf8, false),
        Field::new("token_symbol", DataType::Utf8, true),
        // Balance data
        Field::new("balance", DataType::Decimal128(38, 18), false),
        Field::new("balance_usd", DataType::Decimal128(18, 8), true),
        Field::new("price_at_snapshot", DataType::Decimal128(18, 8), true),
        // Block context
        Field::new("block_number", DataType::Int64, false),
        Field::new(
            "snapshot_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the token_ohlcv table
///
/// Pre-aggregated OHLCV candles for efficient time-series queries.
/// Partitioning: chain_id → interval → block_date
/// Z-order: token_address, interval_start
pub fn token_ohlcv_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        Field::new("shard", DataType::Int32, false),
        // Token identification
        Field::new("token_address", DataType::Utf8, false),
        Field::new("token_symbol", DataType::Utf8, true),
        // Interval
        Field::new("interval", DataType::Utf8, false), // "1m", "5m", "15m", "1h", "4h", "1d"
        Field::new(
            "interval_start",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        // OHLCV data
        Field::new("open", DataType::Decimal128(18, 8), false),
        Field::new("high", DataType::Decimal128(18, 8), false),
        Field::new("low", DataType::Decimal128(18, 8), false),
        Field::new("close", DataType::Decimal128(18, 8), false),
        Field::new("volume_token", DataType::Decimal128(38, 18), false),
        Field::new("volume_usd", DataType::Decimal128(18, 8), false),
        Field::new("vwap", DataType::Decimal128(18, 8), true), // Volume-weighted average price
        Field::new("trade_count", DataType::Int64, false),
        // Source
        Field::new("source_pool", DataType::Utf8, true), // Primary DEX pool
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the wallet_balances table
///
/// Stores wallet token balances with timestamps for alert evaluation.
/// Used by the alert system for lazy field resolution - balances are fetched
/// only when an alert's expression requires balance data.
///
/// Partitioning: chain_id → wallet_address (first 4 chars) → snapshot_date
/// Z-order: wallet_address, token_address, snapshot_timestamp
pub fn wallet_balances_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // ═══════════════════════════════════════════════════════════════════════════
        // PARTITION COLUMNS
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("chain_id", DataType::Int32, false),
        Field::new("snapshot_date", DataType::Date32, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // WALLET AND TOKEN IDENTIFICATION
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("wallet_address", DataType::Utf8, false),
        Field::new("token_address", DataType::Utf8, false),
        Field::new("token_symbol", DataType::Utf8, true),
        Field::new("token_decimals", DataType::Int32, true),
        // ═══════════════════════════════════════════════════════════════════════════
        // BALANCE DATA
        // Uses Decimal128 with high precision for large token balances
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("balance", DataType::Decimal128(38, 0), false), // Raw balance in smallest unit
        Field::new("balance_formatted", DataType::Float64, true),  // Human-readable format
        Field::new("balance_usd", DataType::Float64, true),        // USD value at snapshot
        // ═══════════════════════════════════════════════════════════════════════════
        // SNAPSHOT CONTEXT
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new(
            "snapshot_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new("block_number", DataType::Int64, true),
        // ═══════════════════════════════════════════════════════════════════════════
        // PROCESSING METADATA
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the address_index table
///
/// Index table for fast address lookup across chains.
/// Partitioning: chain_id → address_prefix → shard
/// Z-order: address, chain_id
pub fn address_index_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("address_prefix", DataType::Utf8, false), // First 4 hex chars
        Field::new("shard", DataType::Int32, false),
        // Address identification
        Field::new("address", DataType::Utf8, false),
        Field::new("address_type", DataType::Utf8, false), // wallet, contract, token, pool
        // Activity tracking
        Field::new("first_seen_block", DataType::Int64, false),
        Field::new("first_seen_date", DataType::Date32, false),
        Field::new("last_seen_block", DataType::Int64, false),
        Field::new("last_seen_date", DataType::Date32, false),
        // Statistics
        Field::new("transaction_count", DataType::Int64, false),
        Field::new("token_transfer_count", DataType::Int64, false),
        Field::new("unique_counterparties", DataType::Int32, true),
        // Contract metadata
        Field::new("is_contract", DataType::Boolean, false),
        Field::new("contract_name", DataType::Utf8, true), // If verified
        Field::new("token_symbol", DataType::Utf8, true),  // If token contract
        Field::new("labels", DataType::Utf8, true),        // JSON array: ["dex", "nft", "defi"]
        // Processing metadata
        Field::new(
            "updated_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

// =============================================================================
// NEW TABLES (Schema Redesign)
// =============================================================================

/// Create Arrow schema for the token_transfers table
///
/// Specialized table for token transfers (ERC20/721/1155) extracted from logs.
/// Optimized for token-specific queries and analytics.
///
/// Partitioning: chain_id → year(block_timestamp) → month → day
/// Z-order: from_address, to_address, token_address
pub fn token_transfers_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // ═══════════════════════════════════════════════════════════════════════════
        // PARTITION COLUMNS (function-based)
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // PRIMARY IDENTIFIERS
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("block_number", DataType::Int64, false),
        Field::new(
            "block_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new("transaction_hash", DataType::Utf8, false),
        Field::new("log_index", DataType::Int32, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // TOKEN IDENTIFICATION
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("token_address", DataType::Utf8, false),
        Field::new("token_type", DataType::Utf8, false), // ERC20, ERC721, ERC1155
        Field::new("token_symbol", DataType::Utf8, true),
        Field::new("token_name", DataType::Utf8, true),
        Field::new("token_decimals", DataType::Int32, true),
        // ═══════════════════════════════════════════════════════════════════════════
        // TRANSFER DATA
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("from_address", DataType::Utf8, false),
        Field::new("to_address", DataType::Utf8, false),
        Field::new("amount", DataType::Decimal128(38, 18), false),
        Field::new("token_id", DataType::Utf8, true), // For NFTs (ERC721/ERC1155)
        // ═══════════════════════════════════════════════════════════════════════════
        // VALUE ENRICHMENT
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("amount_usd", DataType::Float64, true),
        Field::new("price_at_transfer", DataType::Float64, true), // Token price at transfer time
        // ═══════════════════════════════════════════════════════════════════════════
        // PROCESSING METADATA
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the address_transactions index table
///
/// Materialized index for fast "from OR to = address" queries.
/// Stores one row per address per transaction (two rows for from and to).
///
/// Partitioning: chain_id → year(block_timestamp) → month
/// Z-order: address, block_number
pub fn address_transactions_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // ═══════════════════════════════════════════════════════════════════════════
        // PARTITION COLUMNS (function-based)
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("chain_id", DataType::Utf8, false),
        Field::new("block_date", DataType::Date32, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // INDEX KEY
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("address", DataType::Utf8, false),
        Field::new("transaction_hash", DataType::Utf8, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // TRANSACTION CONTEXT
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("block_number", DataType::Int64, false),
        Field::new(
            "block_timestamp",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new("is_sender", DataType::Boolean, false), // true = from_address, false = to_address
        Field::new("counterparty_address", DataType::Utf8, true), // The other address in the transaction
        // ═══════════════════════════════════════════════════════════════════════════
        // SUMMARY DATA (denormalized for fast lookups)
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("value", DataType::Decimal128(38, 18), true),
        Field::new("transaction_type", DataType::Utf8, true), // TRANSFER, CONTRACT_CALL, etc.
        Field::new("transaction_subtype", DataType::Utf8, true), // native, erc20, etc.
        // ═══════════════════════════════════════════════════════════════════════════
        // PROCESSING METADATA
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

// =============================================================================
// Operational Tables (Existing)
// =============================================================================

/// Create Arrow schema for the notification_deliveries table
///
/// Stores delivery attempt metrics for each notification channel.
/// One notification may have multiple delivery records (one per channel/attempt).
///
/// Partitioning: delivery_date → channel_type → shard
/// Z-order: channel_id, delivery_status, started_at, endpoint_url
pub fn notification_deliveries_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // Partition columns (using time-based partitioning instead of blockchain partitions)
        Field::new("delivery_date", DataType::Date32, false),
        Field::new("channel_type", DataType::Utf8, false),
        Field::new("shard", DataType::Int32, false),
        // Primary identifiers
        Field::new("notification_id", DataType::Utf8, false),
        Field::new("channel_id", DataType::Utf8, false),
        Field::new("endpoint_url", DataType::Utf8, true),
        // Foreign key to notification_content table
        Field::new("content_notification_id", DataType::Utf8, true),
        // Endpoint metadata
        Field::new("endpoint_id", DataType::Utf8, true),
        Field::new("endpoint_label", DataType::Utf8, true),
        // Delivery attempt tracking
        Field::new("attempt_number", DataType::Int32, false),
        Field::new("max_attempts", DataType::Int32, false),
        Field::new("delivery_status", DataType::Utf8, false),
        // Timing metrics
        Field::new(
            "started_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new(
            "completed_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            true,
        ),
        Field::new("response_time_ms", DataType::Int64, true),
        // Response data
        Field::new("http_status_code", DataType::Int32, true),
        Field::new("response_body", DataType::Utf8, true),
        Field::new("error_message", DataType::Utf8, true),
        Field::new("error_type", DataType::Utf8, true),
        // Notification content metadata
        Field::new("alert_id", DataType::Utf8, true),
        Field::new("transaction_hash", DataType::Utf8, true),
        Field::new("severity", DataType::Utf8, true),
        Field::new("message_size_bytes", DataType::Int32, true),
        // Retry and fallback tracking
        Field::new("used_fallback", DataType::Boolean, false),
        Field::new("fallback_url", DataType::Utf8, true),
        Field::new("retry_delay_ms", DataType::Int64, true),
        // Provider metadata
        Field::new("provider_id", DataType::Utf8, true),
        Field::new("provider_version", DataType::Utf8, true),
        // Processing metadata
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Create Arrow schema for the notification_content table
///
/// Stores notification content (messages) for historical queries and user notification history.
/// Each notification is stored once; delivery attempts are tracked in notification_deliveries.
///
/// Partitioning: notification_date → user_id_prefix → shard
/// Z-order: user_id, alert_id, created_at, notification_id
pub fn notification_content_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        // ═══════════════════════════════════════════════════════════════════════════
        // PARTITION COLUMNS
        // Partitioning: notification_date → user_id_prefix (first 8 chars) → shard
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("notification_date", DataType::Date32, false),
        Field::new("user_id_prefix", DataType::Utf8, false), // First 8 chars of user_id for distribution
        Field::new("shard", DataType::Int32, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // PRIMARY IDENTIFIERS
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("notification_id", DataType::Utf8, false), // UUID, primary key
        Field::new("user_id", DataType::Utf8, false),
        Field::new("group_id", DataType::Utf8, true), // Optional team/group ID
        Field::new("alert_id", DataType::Utf8, false),
        Field::new("alert_name", DataType::Utf8, false),
        // ═══════════════════════════════════════════════════════════════════════════
        // NOTIFICATION CONTENT
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("title", DataType::Utf8, false),
        Field::new("message", DataType::Utf8, false),
        Field::new("priority", DataType::Utf8, false), // critical, high, medium, normal, low
        // Rich content (JSON for flexibility)
        Field::new("details", DataType::Utf8, true), // JSON: HashMap<String, Value>
        Field::new("template_name", DataType::Utf8, true),
        Field::new("template_variables", DataType::Utf8, true), // JSON: HashMap<String, String>
        Field::new("actions", DataType::Utf8, true),            // JSON: Vec<NotificationAction>
        // ═══════════════════════════════════════════════════════════════════════════
        // TRANSACTION CONTEXT (blockchain data that triggered notification)
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("transaction_hash", DataType::Utf8, true),
        Field::new("chain_id", DataType::Utf8, true),
        Field::new("block_number", DataType::Int64, true),
        Field::new("from_address", DataType::Utf8, true),
        Field::new("to_address", DataType::Utf8, true),
        Field::new("contract_address", DataType::Utf8, true),
        Field::new("value", DataType::Utf8, true), // Transaction value as string
        Field::new("value_usd", DataType::Float64, true),
        // ═══════════════════════════════════════════════════════════════════════════
        // DELIVERY TRACKING SUMMARY
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new("target_channels", DataType::Utf8, true), // JSON: Vec<String> - channels to deliver to
        Field::new("delivery_status", DataType::Utf8, false), // pending, partial, delivered, failed
        Field::new("channels_delivered", DataType::Int32, false),
        Field::new("channels_failed", DataType::Int32, false),
        Field::new(
            "first_delivery_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            true,
        ),
        Field::new(
            "all_delivered_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            true,
        ),
        // ═══════════════════════════════════════════════════════════════════════════
        // TIMESTAMPS
        // ═══════════════════════════════════════════════════════════════════════════
        Field::new(
            "created_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
        Field::new(
            "ingested_at",
            DataType::Timestamp(TimeUnit::Microsecond, None),
            false,
        ),
    ]))
}

/// Table names as defined in the PRD
pub const BLOCKS_TABLE: &str = "blocks";
pub const TRANSACTIONS_TABLE: &str = "transactions";
pub const LOGS_TABLE: &str = "logs";
pub const TOKEN_PRICES_TABLE: &str = "token_prices";
pub const PROTOCOL_EVENTS_TABLE: &str = "protocol_events";
pub const CONTRACT_CALLS_TABLE: &str = "contract_calls";
pub const NOTIFICATION_DELIVERIES_TABLE: &str = "notification_deliveries";
pub const NOTIFICATION_CONTENT_TABLE: &str = "notification_content";

// ═══════════════════════════════════════════════════════════════════════════
// DEPRECATED: VM-specific transaction tables (Schema Redesign)
// These tables are deprecated in favor of the unified `transactions` table.
// Use vm_type field ('evm', 'svm', 'utxo') to filter by VM type.
// Kept for backward compatibility during transition period.
// ═══════════════════════════════════════════════════════════════════════════
#[deprecated(
    since = "0.2.0",
    note = "Use TRANSACTIONS_TABLE with vm_type='evm' instead"
)]
pub const TRANSACTIONS_EVM_TABLE: &str = "transactions_evm";
#[deprecated(
    since = "0.2.0",
    note = "Use TRANSACTIONS_TABLE with vm_type='svm' instead"
)]
pub const TRANSACTIONS_SVM_TABLE: &str = "transactions_svm";
#[deprecated(
    since = "0.2.0",
    note = "Use TRANSACTIONS_TABLE with vm_type='utxo' instead"
)]
pub const TRANSACTIONS_BTC_TABLE: &str = "transactions_btc";

// ═══════════════════════════════════════════════════════════════════════════
// DEPRECATED: Decoded transaction tables (Schema Redesign)
// Decoded fields are now part of the unified `transactions` table.
// Use decoded_function_name, decoded_parameters, etc. fields directly.
// ═══════════════════════════════════════════════════════════════════════════
#[deprecated(
    since = "0.2.0",
    note = "Use TRANSACTIONS_TABLE with decoded_* fields instead"
)]
pub const DECODED_TRANSACTIONS_EVM_TABLE: &str = "decoded_transactions_evm";

// ═══════════════════════════════════════════════════════════════════════════
// DEPRECATED: Processed transfers table (Schema Redesign)
// Enrichment fields are now part of the unified `transactions` table.
// Use amount_native, amount_usd, transfer_category, etc. fields directly.
// ═══════════════════════════════════════════════════════════════════════════
#[deprecated(
    since = "0.2.0",
    note = "Use TRANSACTIONS_TABLE with enrichment fields instead"
)]
pub const PROCESSED_TRANSFERS_TABLE: &str = "processed_transfers";
pub const WALLET_ACTIVITY_TABLE: &str = "wallet_activity";
pub const LP_POSITIONS_TABLE: &str = "lp_positions";
pub const YIELD_EVENTS_TABLE: &str = "yield_events";
pub const TOKEN_HOLDINGS_TABLE: &str = "token_holdings";
pub const TOKEN_OHLCV_TABLE: &str = "token_ohlcv";
pub const ADDRESS_INDEX_TABLE: &str = "address_index";

// Alert System Tables (Lazy Field Resolution)
pub const WALLET_BALANCES_TABLE: &str = "wallet_balances";

// NEW: Unified Schema Tables (Schema Redesign)
pub const TOKEN_TRANSFERS_TABLE: &str = "token_transfers";
pub const ADDRESS_TRANSACTIONS_TABLE: &str = "address_transactions";

/// Get schema for a table by name
///
/// Supports both current and deprecated table names for backward compatibility.
/// Deprecated tables (transactions_evm, transactions_svm, transactions_btc,
/// decoded_transactions_evm, processed_transfers) map to the unified transactions schema.
#[allow(deprecated)]
pub fn get_schema_for_table(table_name: &str) -> Option<Arc<Schema>> {
    match table_name {
        BLOCKS_TABLE => Some(blocks_schema()),
        TRANSACTIONS_TABLE => Some(transactions_schema()),
        // DEPRECATED: VM-specific transaction tables use the unified transactions schema
        TRANSACTIONS_EVM_TABLE => Some(transactions_schema()),
        TRANSACTIONS_SVM_TABLE => Some(transactions_schema()),
        TRANSACTIONS_BTC_TABLE => Some(transactions_schema()),
        // DEPRECATED: Decoded transactions use unified transactions schema
        DECODED_TRANSACTIONS_EVM_TABLE => Some(transactions_schema()),
        LOGS_TABLE => Some(logs_schema()),
        TOKEN_PRICES_TABLE => Some(token_prices_schema()),
        PROTOCOL_EVENTS_TABLE => Some(protocol_events_schema()),
        CONTRACT_CALLS_TABLE => Some(contract_calls_schema()),
        NOTIFICATION_DELIVERIES_TABLE => Some(notification_deliveries_schema()),
        NOTIFICATION_CONTENT_TABLE => Some(notification_content_schema()),
        // DeFi Analytics Tables
        // DEPRECATED: processed_transfers uses its own schema but is deprecated
        PROCESSED_TRANSFERS_TABLE => Some(processed_transfers_schema()),
        WALLET_ACTIVITY_TABLE => Some(wallet_activity_schema()),
        LP_POSITIONS_TABLE => Some(lp_positions_schema()),
        YIELD_EVENTS_TABLE => Some(yield_events_schema()),
        TOKEN_HOLDINGS_TABLE => Some(token_holdings_schema()),
        TOKEN_OHLCV_TABLE => Some(token_ohlcv_schema()),
        ADDRESS_INDEX_TABLE => Some(address_index_schema()),
        // Alert System Tables (Lazy Field Resolution)
        WALLET_BALANCES_TABLE => Some(wallet_balances_schema()),
        // NEW: Unified Schema Tables (Schema Redesign)
        TOKEN_TRANSFERS_TABLE => Some(token_transfers_schema()),
        ADDRESS_TRANSACTIONS_TABLE => Some(address_transactions_schema()),
        _ => None,
    }
}

/// Get all table names (including deprecated tables for backward compatibility)
#[allow(deprecated)]
pub fn get_all_table_names() -> Vec<&'static str> {
    vec![
        // Core blockchain tables
        BLOCKS_TABLE,
        TRANSACTIONS_TABLE,
        LOGS_TABLE,
        TOKEN_PRICES_TABLE,
        PROTOCOL_EVENTS_TABLE,
        CONTRACT_CALLS_TABLE,
        NOTIFICATION_DELIVERIES_TABLE,
        NOTIFICATION_CONTENT_TABLE,
        // DEPRECATED: VM-specific transaction tables (kept for backward compatibility)
        TRANSACTIONS_EVM_TABLE,
        TRANSACTIONS_SVM_TABLE,
        TRANSACTIONS_BTC_TABLE,
        // DEPRECATED: Decoded transaction tables
        DECODED_TRANSACTIONS_EVM_TABLE,
        // DeFi Analytics Tables
        // DEPRECATED: processed_transfers
        PROCESSED_TRANSFERS_TABLE,
        WALLET_ACTIVITY_TABLE,
        LP_POSITIONS_TABLE,
        YIELD_EVENTS_TABLE,
        TOKEN_HOLDINGS_TABLE,
        TOKEN_OHLCV_TABLE,
        ADDRESS_INDEX_TABLE,
        // Alert System Tables (Lazy Field Resolution)
        WALLET_BALANCES_TABLE,
        // NEW: Unified Schema Tables (Schema Redesign)
        TOKEN_TRANSFERS_TABLE,
        ADDRESS_TRANSACTIONS_TABLE,
    ]
}

/// Partition specification for 3-level partitioning
pub fn get_partition_columns() -> Vec<String> {
    vec![
        "chain_id".to_string(),
        "block_date".to_string(),
        "shard".to_string(),
    ]
}

/// Get partition columns for a specific table
///
/// Different tables use different partitioning strategies:
/// - Standard blockchain tables: chain_id → block_date → shard
/// - Address-based tables: chain_id → address_prefix → block_date (or shard)
/// - Time-series tables: chain_id → interval → block_date
/// - Operational tables: delivery_date → channel_type → shard
/// - NEW: Function-based tables (Schema Redesign): chain_id → block_date (no shard, use time functions)
#[allow(deprecated)]
pub fn get_partition_columns_for_table(table_name: &str) -> Vec<String> {
    match table_name {
        // Operational tables
        NOTIFICATION_DELIVERIES_TABLE => vec![
            "delivery_date".to_string(),
            "channel_type".to_string(),
            "shard".to_string(),
        ],
        // Notification content uses user-centric partitioning for efficient user history queries
        NOTIFICATION_CONTENT_TABLE => vec![
            "notification_date".to_string(),
            "user_id_prefix".to_string(),
            "shard".to_string(),
        ],
        // Address-prefix partitioned tables
        WALLET_ACTIVITY_TABLE | ADDRESS_INDEX_TABLE => vec![
            "chain_id".to_string(),
            "address_prefix".to_string(),
            "block_date".to_string(),
            "shard".to_string(),
        ],
        // Snapshot tables
        TOKEN_HOLDINGS_TABLE | WALLET_BALANCES_TABLE => {
            vec!["chain_id".to_string(), "snapshot_date".to_string()]
        }
        // NEW: Function-based partitioning (Schema Redesign)
        // These tables use chain_id → year(ts) → month(ts) → day(ts) partitioning
        // block_date is stored for compatibility but partitioning uses timestamp functions
        // The actual partitioning is done via DuckDB functions on block_timestamp
        TRANSACTIONS_TABLE
        | TRANSACTIONS_EVM_TABLE
        | TRANSACTIONS_SVM_TABLE
        | TRANSACTIONS_BTC_TABLE
        | DECODED_TRANSACTIONS_EVM_TABLE
        | LOGS_TABLE
        | CONTRACT_CALLS_TABLE
        | TOKEN_TRANSFERS_TABLE
        | ADDRESS_TRANSACTIONS_TABLE => vec!["chain_id".to_string(), "block_date".to_string()],
        // Standard 3-level partitioning for tables that still need explicit sharding
        _ => get_partition_columns(),
    }
}

/// Z-order columns for query optimization (per table)
///
/// Z-ordering improves query performance for multi-dimensional filters.
/// Columns are listed in order of filter priority.
#[allow(deprecated)]
pub fn get_z_order_columns(table_name: &str) -> Vec<String> {
    match table_name {
        // Core blockchain tables
        BLOCKS_TABLE => vec!["block_number".to_string(), "block_hash".to_string()],
        TRANSACTIONS_TABLE => vec![
            "block_number".to_string(),
            "transaction_index".to_string(),
            "from_address".to_string(),
            "to_address".to_string(),
            "method_signature".to_string(), // Added for contract monitoring
        ],
        LOGS_TABLE => vec![
            "block_number".to_string(),
            "transaction_hash".to_string(),
            "address".to_string(),
            "topic0".to_string(),
            "is_transfer".to_string(), // Added for hot boolean filters
            "is_swap".to_string(),
        ],
        TOKEN_PRICES_TABLE => vec![
            "block_number".to_string(),
            "token_address".to_string(),
            "source_type".to_string(),
        ],
        PROTOCOL_EVENTS_TABLE => vec![
            "user_address".to_string(), // Reordered: user-centric queries first
            "protocol_name".to_string(),
            "event_category".to_string(),
            "block_number".to_string(),
        ],
        CONTRACT_CALLS_TABLE => vec![
            "block_number".to_string(),
            "transaction_hash".to_string(),
            "from_address".to_string(),
            "to_address".to_string(),
        ],
        // Operational tables
        NOTIFICATION_DELIVERIES_TABLE => vec![
            "channel_id".to_string(),
            "delivery_status".to_string(),
            "started_at".to_string(),
            "endpoint_url".to_string(),
        ],
        // Notification content z-order for user history queries
        NOTIFICATION_CONTENT_TABLE => vec![
            "user_id".to_string(),
            "alert_id".to_string(),
            "created_at".to_string(),
            "priority".to_string(),
        ],
        // DeFi Analytics Tables
        PROCESSED_TRANSFERS_TABLE => vec![
            "from_address".to_string(),
            "to_address".to_string(),
            "block_number".to_string(),
            "transaction_hash".to_string(),
        ],
        WALLET_ACTIVITY_TABLE => vec![
            "wallet_address".to_string(),
            "block_number".to_string(),
            "token_address".to_string(),
        ],
        LP_POSITIONS_TABLE => vec![
            "user_address".to_string(),
            "pool_address".to_string(),
            "block_number".to_string(),
        ],
        YIELD_EVENTS_TABLE => vec![
            "user_address".to_string(),
            "protocol_name".to_string(),
            "block_number".to_string(),
        ],
        TOKEN_HOLDINGS_TABLE => vec![
            "wallet_address".to_string(),
            "token_address".to_string(),
            "block_number".to_string(),
        ],
        // Alert System Tables (Lazy Field Resolution)
        WALLET_BALANCES_TABLE => vec![
            "wallet_address".to_string(),
            "token_address".to_string(),
            "snapshot_timestamp".to_string(),
        ],
        TOKEN_OHLCV_TABLE => vec!["token_address".to_string(), "interval_start".to_string()],
        ADDRESS_INDEX_TABLE => vec!["address".to_string(), "chain_id".to_string()],
        // NEW: Unified Schema Tables (Schema Redesign)
        TOKEN_TRANSFERS_TABLE => vec![
            "from_address".to_string(),
            "to_address".to_string(),
            "token_address".to_string(),
            "block_number".to_string(),
        ],
        ADDRESS_TRANSACTIONS_TABLE => vec!["address".to_string(), "block_number".to_string()],
        _ => vec!["block_number".to_string()],
    }
}

#[cfg(test)]
#[allow(deprecated)]
mod tests {
    use super::*;

    #[test]
    fn test_all_schemas_valid() {
        // Core blockchain tables
        assert!(!blocks_schema().fields().is_empty());
        assert!(!transactions_schema().fields().is_empty());
        assert!(!logs_schema().fields().is_empty());
        assert!(!token_prices_schema().fields().is_empty());
        assert!(!protocol_events_schema().fields().is_empty());
        assert!(!contract_calls_schema().fields().is_empty());
        assert!(!notification_deliveries_schema().fields().is_empty());
        assert!(!notification_content_schema().fields().is_empty());
        // DeFi Analytics tables
        assert!(!wallet_activity_schema().fields().is_empty());
        assert!(!lp_positions_schema().fields().is_empty());
        assert!(!yield_events_schema().fields().is_empty());
        assert!(!token_holdings_schema().fields().is_empty());
        assert!(!token_ohlcv_schema().fields().is_empty());
        assert!(!address_index_schema().fields().is_empty());
        // Alert System tables
        assert!(!wallet_balances_schema().fields().is_empty());
        // NEW: Unified Schema Tables (Schema Redesign)
        assert!(!token_transfers_schema().fields().is_empty());
        assert!(!address_transactions_schema().fields().is_empty());
    }

    #[test]
    fn test_get_schema_for_table() {
        // Core tables
        assert!(get_schema_for_table(BLOCKS_TABLE).is_some());
        assert!(get_schema_for_table(TRANSACTIONS_TABLE).is_some());
        // DeFi tables
        assert!(get_schema_for_table(WALLET_ACTIVITY_TABLE).is_some());
        assert!(get_schema_for_table(LP_POSITIONS_TABLE).is_some());
        assert!(get_schema_for_table(YIELD_EVENTS_TABLE).is_some());
        assert!(get_schema_for_table(TOKEN_HOLDINGS_TABLE).is_some());
        assert!(get_schema_for_table(TOKEN_OHLCV_TABLE).is_some());
        assert!(get_schema_for_table(ADDRESS_INDEX_TABLE).is_some());
        // Notification tables
        assert!(get_schema_for_table(NOTIFICATION_CONTENT_TABLE).is_some());
        // NEW: Unified Schema Tables (Schema Redesign)
        assert!(get_schema_for_table(TOKEN_TRANSFERS_TABLE).is_some());
        assert!(get_schema_for_table(ADDRESS_TRANSACTIONS_TABLE).is_some());
        // Nonexistent
        assert!(get_schema_for_table("nonexistent").is_none());
    }

    #[test]
    fn test_partition_columns() {
        let partition_cols = get_partition_columns();
        assert_eq!(partition_cols.len(), 3);
        assert!(partition_cols.contains(&"chain_id".to_string()));
        assert!(partition_cols.contains(&"block_date".to_string()));
        assert!(partition_cols.contains(&"shard".to_string()));
    }

    #[test]
    fn test_partition_columns_for_address_tables() {
        // Address-prefix partitioned tables have 4 columns
        let wallet_cols = get_partition_columns_for_table(WALLET_ACTIVITY_TABLE);
        assert_eq!(wallet_cols.len(), 4);
        assert!(wallet_cols.contains(&"address_prefix".to_string()));

        let addr_cols = get_partition_columns_for_table(ADDRESS_INDEX_TABLE);
        assert_eq!(addr_cols.len(), 4);
        assert!(addr_cols.contains(&"address_prefix".to_string()));
    }

    #[test]
    fn test_partition_columns_for_snapshot_tables() {
        let holdings_cols = get_partition_columns_for_table(TOKEN_HOLDINGS_TABLE);
        assert_eq!(holdings_cols.len(), 2); // chain_id, snapshot_date (no shard for snapshots)
        assert!(holdings_cols.contains(&"chain_id".to_string()));
        assert!(holdings_cols.contains(&"snapshot_date".to_string()));
    }

    #[test]
    fn test_all_table_names() {
        let all_tables = get_all_table_names();
        assert_eq!(all_tables.len(), 22); // 9 core + 4 VM-specific + 1 decoded + 6 DeFi + 2 new unified
                                          // Core tables
        assert!(all_tables.contains(&BLOCKS_TABLE));
        assert!(all_tables.contains(&TRANSACTIONS_TABLE));
        assert!(all_tables.contains(&NOTIFICATION_DELIVERIES_TABLE));
        assert!(all_tables.contains(&NOTIFICATION_CONTENT_TABLE));
        // DeFi tables
        assert!(all_tables.contains(&WALLET_ACTIVITY_TABLE));
        assert!(all_tables.contains(&LP_POSITIONS_TABLE));
        assert!(all_tables.contains(&YIELD_EVENTS_TABLE));
        assert!(all_tables.contains(&TOKEN_HOLDINGS_TABLE));
        assert!(all_tables.contains(&TOKEN_OHLCV_TABLE));
        assert!(all_tables.contains(&ADDRESS_INDEX_TABLE));
        // NEW: Unified Schema Tables (Schema Redesign)
        assert!(all_tables.contains(&TOKEN_TRANSFERS_TABLE));
        assert!(all_tables.contains(&ADDRESS_TRANSACTIONS_TABLE));
    }

    #[test]
    fn test_z_order_columns_defi_tables() {
        // Wallet activity should have wallet_address first
        let wallet_z = get_z_order_columns(WALLET_ACTIVITY_TABLE);
        assert_eq!(wallet_z[0], "wallet_address");

        // LP positions should have user_address first
        let lp_z = get_z_order_columns(LP_POSITIONS_TABLE);
        assert_eq!(lp_z[0], "user_address");

        // Token OHLCV should have token_address and interval_start
        let ohlcv_z = get_z_order_columns(TOKEN_OHLCV_TABLE);
        assert!(ohlcv_z.contains(&"token_address".to_string()));
        assert!(ohlcv_z.contains(&"interval_start".to_string()));
    }

    #[test]
    fn test_transactions_z_order_includes_method_signature() {
        let tx_z = get_z_order_columns(TRANSACTIONS_TABLE);
        assert!(tx_z.contains(&"method_signature".to_string()));
    }

    #[test]
    fn test_logs_z_order_includes_boolean_filters() {
        let logs_z = get_z_order_columns(LOGS_TABLE);
        assert!(logs_z.contains(&"is_transfer".to_string()));
        assert!(logs_z.contains(&"is_swap".to_string()));
    }

    #[test]
    fn test_new_unified_schema_tables() {
        // Token transfers schema should have all required fields
        let tt_schema = token_transfers_schema();
        let tt_fields: Vec<&str> = tt_schema
            .fields()
            .iter()
            .map(|f| f.name().as_str())
            .collect();
        assert!(tt_fields.contains(&"chain_id"));
        assert!(tt_fields.contains(&"token_address"));
        assert!(tt_fields.contains(&"token_type"));
        assert!(tt_fields.contains(&"from_address"));
        assert!(tt_fields.contains(&"to_address"));
        assert!(tt_fields.contains(&"amount"));
        assert!(tt_fields.contains(&"amount_usd"));

        // Address transactions schema should have all required fields
        let at_schema = address_transactions_schema();
        let at_fields: Vec<&str> = at_schema
            .fields()
            .iter()
            .map(|f| f.name().as_str())
            .collect();
        assert!(at_fields.contains(&"chain_id"));
        assert!(at_fields.contains(&"address"));
        assert!(at_fields.contains(&"transaction_hash"));
        assert!(at_fields.contains(&"is_sender"));
        assert!(at_fields.contains(&"counterparty_address"));
    }

    #[test]
    fn test_new_tables_partition_columns() {
        // New unified tables use function-based partitioning (no shard column)
        let tt_cols = get_partition_columns_for_table(TOKEN_TRANSFERS_TABLE);
        assert_eq!(tt_cols.len(), 2);
        assert!(tt_cols.contains(&"chain_id".to_string()));
        assert!(tt_cols.contains(&"block_date".to_string()));
        assert!(!tt_cols.contains(&"shard".to_string())); // No explicit shard

        let at_cols = get_partition_columns_for_table(ADDRESS_TRANSACTIONS_TABLE);
        assert_eq!(at_cols.len(), 2);
        assert!(at_cols.contains(&"chain_id".to_string()));
        assert!(at_cols.contains(&"block_date".to_string()));
        assert!(!at_cols.contains(&"shard".to_string()));
    }

    #[test]
    fn test_new_tables_z_order_columns() {
        // Token transfers should have address-centric z-ordering
        let tt_z = get_z_order_columns(TOKEN_TRANSFERS_TABLE);
        assert!(tt_z.contains(&"from_address".to_string()));
        assert!(tt_z.contains(&"to_address".to_string()));
        assert!(tt_z.contains(&"token_address".to_string()));

        // Address transactions should have address as primary z-order
        let at_z = get_z_order_columns(ADDRESS_TRANSACTIONS_TABLE);
        assert_eq!(at_z[0], "address");
        assert!(at_z.contains(&"block_number".to_string()));
    }

    #[test]
    fn test_transactions_schema_has_decoded_fields() {
        let schema = transactions_schema();
        let fields: Vec<&str> = schema.fields().iter().map(|f| f.name().as_str()).collect();

        // Decoded function fields
        assert!(fields.contains(&"decoded_function_name"));
        assert!(fields.contains(&"decoded_function_signature"));
        assert!(fields.contains(&"decoded_function_selector"));
        assert!(fields.contains(&"decoded_parameters"));
        assert!(fields.contains(&"decoding_status"));
        assert!(fields.contains(&"abi_source"));
        assert!(fields.contains(&"decoding_time_ms"));
        assert!(fields.contains(&"decoded_summary"));

        // Value enrichment fields
        assert!(fields.contains(&"transaction_type"));
        assert!(fields.contains(&"transaction_subtype"));
        assert!(fields.contains(&"amount_native"));
        assert!(fields.contains(&"amount_usd"));
        assert!(fields.contains(&"transfer_category"));
    }

    #[test]
    fn test_logs_schema_has_decoded_event_fields() {
        let schema = logs_schema();
        let fields: Vec<&str> = schema.fields().iter().map(|f| f.name().as_str()).collect();

        // Decoded event fields
        assert!(fields.contains(&"decoded_event_name"));
        assert!(fields.contains(&"decoded_event_signature"));
        assert!(fields.contains(&"decoded_event_parameters"));
        assert!(fields.contains(&"event_decoding_status"));
        assert!(fields.contains(&"is_anonymous_event"));
    }

    #[test]
    fn test_notification_content_schema() {
        // Schema should have all required fields
        let schema = notification_content_schema();
        let fields: Vec<&str> = schema.fields().iter().map(|f| f.name().as_str()).collect();

        // Partition columns
        assert!(fields.contains(&"notification_date"));
        assert!(fields.contains(&"user_id_prefix"));
        assert!(fields.contains(&"shard"));

        // Primary identifiers
        assert!(fields.contains(&"notification_id"));
        assert!(fields.contains(&"user_id"));
        assert!(fields.contains(&"alert_id"));
        assert!(fields.contains(&"alert_name"));

        // Notification content
        assert!(fields.contains(&"title"));
        assert!(fields.contains(&"message"));
        assert!(fields.contains(&"priority"));
        assert!(fields.contains(&"details"));
        assert!(fields.contains(&"template_name"));

        // Transaction context
        assert!(fields.contains(&"transaction_hash"));
        assert!(fields.contains(&"chain_id"));
        assert!(fields.contains(&"value_usd"));

        // Delivery tracking
        assert!(fields.contains(&"delivery_status"));
        assert!(fields.contains(&"channels_delivered"));
        assert!(fields.contains(&"channels_failed"));
    }

    #[test]
    fn test_notification_content_partition_columns() {
        let cols = get_partition_columns_for_table(NOTIFICATION_CONTENT_TABLE);
        assert_eq!(cols.len(), 3);
        assert!(cols.contains(&"notification_date".to_string()));
        assert!(cols.contains(&"user_id_prefix".to_string()));
        assert!(cols.contains(&"shard".to_string()));
    }

    #[test]
    fn test_notification_content_z_order_columns() {
        let z_cols = get_z_order_columns(NOTIFICATION_CONTENT_TABLE);
        assert_eq!(z_cols[0], "user_id"); // User-centric queries first
        assert!(z_cols.contains(&"alert_id".to_string()));
        assert!(z_cols.contains(&"created_at".to_string()));
        assert!(z_cols.contains(&"priority".to_string()));
    }

    #[test]
    fn test_notification_deliveries_has_fk_fields() {
        let schema = notification_deliveries_schema();
        let fields: Vec<&str> = schema.fields().iter().map(|f| f.name().as_str()).collect();

        // FK fields linking to notification_content
        assert!(fields.contains(&"content_notification_id"));
        assert!(fields.contains(&"endpoint_id"));
        assert!(fields.contains(&"endpoint_label"));
    }
}
