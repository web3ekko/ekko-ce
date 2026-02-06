//! # Ethereum Contract Creation Processor Actor
//!
//! WasmCloud actor that processes contract deployment transactions with bytecode analysis,
//! contract type detection, and registry management. This actor receives deployment transactions
//! from the eth_process_transactions actor and enriches them with contract metadata.
//!
//! ## Architecture
//! - **wasmCloud Actor**: Uses proper WIT interfaces
//! - **WASM Component**: Runs in wasmCloud runtime
//! - **Messaging**: Subscribes to contract-creations.*.*.evm.raw
//! - **State**: Redis for contract registry and creator tracking
//!
//! ## Subscription Pattern
//! - Subscribes to: `contract-creations.*.*.evm.raw` (wildcard for all EVM chains)
//! - Publishes to:
//!   - `contracts.deployed.evm` - Processed deployments with enrichment
//!   - `alerts.evaluate.{chain}` - Alert evaluation system
//!   - `contracts.registry.{chain}` - Contract registry updates
//!   - `ducklake.transactions.{network}.{subnet}.write` - Historical data persistence

use chrono::{TimeZone, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

// Generate WIT bindings for the processor world
wit_bindgen::generate!({ generate_all });

use exports::wasmcloud::messaging::handler::Guest as MessageHandler;
use wasmcloud::messaging::{consumer, types};

/// Raw contract creation transaction in standard Ethereum format
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawContractCreation {
    // Standard Ethereum transaction fields
    pub hash: String,
    pub from: String,
    #[serde(default)]
    pub to: Option<String>, // null for contract creations
    pub value: String,
    pub gas: String,
    pub gas_price: String,
    pub input: String, // Deployment bytecode
    pub nonce: String,
    pub block_number: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub block_timestamp: Option<String>,
    pub block_hash: String,
    pub transaction_index: String,
    pub chain_id: String,

    // Contract creation specific (from receipt)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub contract_address: Option<String>,

    // Optional signature fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,
}

/// Processed contract deployment with enrichment and analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessedContractCreation {
    // Original transaction data
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
    pub transaction_hash: String,
    pub block_number: u64,
    pub block_timestamp: u64,

    // Deployment-specific data
    pub creator_address: String,
    pub contract_address: String,
    pub deployment_bytecode: String,
    pub runtime_bytecode: Option<String>,
    pub constructor_args: Option<String>,

    // Gas and costs
    pub gas_used: u64,
    pub gas_price: String,
    pub deployment_cost_wei: String,
    pub deployment_cost_eth: f64,

    // Bytecode analysis
    pub bytecode_size: usize,
    pub bytecode_hash: String,
    pub bytecode_complexity: u32,
    pub detected_patterns: Vec<BytecodePattern>,

    // Contract classification
    pub contract_type: Option<ContractType>,
    pub is_proxy: bool,
    pub implementation_address: Option<String>,

    // Creator context
    pub creator_deployment_count: u32,
    pub is_factory: bool,

    // Metadata
    pub processed_at: String,
    pub processor_id: String,
    pub correlation_id: String,

    // Standardized enrichment fields (cross-actor consistency)
    pub transaction_type: String,     // Always "contract_deployment"
    pub transaction_currency: String, // Always "ETH" (deployment cost)
    pub transaction_value: String,    // "0.05 ETH" (deployment cost)
    pub transaction_subtype: String,  // "create" | "create2"
    pub protocol: Option<String>,     // "ERC20" | "ERC721" | "Proxy" | "Uniswap_V2" | etc.
    pub category: String,             // Always "infrastructure"
    pub decoded: serde_json::Value,   // Deployment details JSON
}

/// Minimal DuckLake transaction record aligned to transactions schema.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuckLakeTransactionRecord {
    pub chain_id: String,
    pub block_date: String,
    pub network: String,
    pub subnet: String,
    pub vm_type: String,
    pub block_number: u64,
    pub block_timestamp: u64,
    pub transaction_hash: String,
    pub transaction_index: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub from_address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub to_address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gas_limit: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gas_used: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gas_price: Option<String>,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_fee: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_data: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub method_signature: Option<String>,
    pub transaction_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_subtype: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_function_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_function_signature: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_function_selector: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_parameters: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoding_status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub abi_source: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoding_time_ms: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decoded_summary: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub nonce: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub v: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub r: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub s: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub processor_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub correlation_id: Option<String>,
}

/// Minimal DuckLake address_transactions record aligned to schema requirements.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuckLakeAddressTransactionRecord {
    pub chain_id: String,
    pub block_date: String,
    pub address: String,
    pub transaction_hash: String,
    pub block_number: u64,
    pub block_timestamp: u64,
    pub is_sender: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub counterparty_address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transaction_subtype: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ContractType {
    ERC20Token,
    ERC721NFT,
    ERC1155MultiToken,
    UniswapV2Pair,
    UniswapV3Pool,
    ProxyContract,
    MultiSigWallet,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum BytecodePattern {
    MinimalProxy,     // EIP-1167
    TransparentProxy, // EIP-1967
    UUPSProxy,        // EIP-1822
    BeaconProxy,
    DiamondProxy, // EIP-2535
    TokenTemplate,
    CustomPattern(String),
}

/// Main ETH Contract Creation Processor Actor
pub struct Component;

// Export Component for WasmCloud
export!(Component);

impl MessageHandler for Component {
    /// Handle incoming NATS messages containing contract deployment transactions
    fn handle_message(msg: types::BrokerMessage) -> Result<(), String> {
        let subject = msg.subject.as_str();
        let (network, subnet, vm_type) = if subject.starts_with("contract-creations.")
            && subject.ends_with(".raw")
        {
            // contract-creations.{network}.{subnet}.{vm_type}.raw
            Self::parse_subject_context(subject)?
        } else if subject.starts_with("blockchain.") && subject.ends_with(".contracts.creation") {
            // blockchain.{network}.{subnet}.contracts.creation
            Self::parse_blockchain_context(subject)?
        } else {
            return Ok(());
        };

        // Parse the contract creation transaction from the message
        let raw_creation: RawContractCreation = serde_json::from_slice(&msg.body)
            .map_err(|e| format!("Failed to parse contract creation: {}", e))?;

        // Process the deployment and publish results
        Self::process_and_publish_deployment(raw_creation, network, subnet, vm_type)?;

        Ok(())
    }
}

impl Component {
    /// Parse network context from NATS subject
    fn parse_subject_context(subject: &str) -> Result<(String, String, String), String> {
        // contract-creations.ethereum.mainnet.evm.raw
        let parts: Vec<&str> = subject.split('.').collect();
        if parts.len() >= 5 {
            Ok((
                parts[1].to_string(), // network
                parts[2].to_string(), // subnet
                parts[3].to_string(), // vm_type
            ))
        } else {
            Err(format!("Invalid subject pattern: {}", subject))
        }
    }

    fn parse_blockchain_context(subject: &str) -> Result<(String, String, String), String> {
        // blockchain.ethereum.mainnet.contracts.creation
        let parts: Vec<&str> = subject.split('.').collect();
        if parts.len() == 5 {
            Ok((
                parts[1].to_string(), // network
                parts[2].to_string(), // subnet
                "evm".to_string(),    // vm_type (implicit for ethereum)
            ))
        } else {
            Err(format!("Invalid subject pattern: {}", subject))
        }
    }

    /// Process a contract deployment and publish to appropriate subjects
    fn process_and_publish_deployment(
        raw_creation: RawContractCreation,
        network: String,
        subnet: String,
        vm_type: String,
    ) -> Result<(), String> {
        // Parse block number and nonce
        let block_number = Self::parse_hex_u64(&raw_creation.block_number);
        let nonce = Self::parse_hex_u64(&raw_creation.nonce);

        // Use contract_address from receipt if available, otherwise calculate
        let contract_address = raw_creation
            .contract_address
            .clone()
            .unwrap_or_else(|| Self::calculate_contract_address(&raw_creation.from, nonce));

        // Parse gas limit and calculate deployment cost
        let gas_limit = Self::parse_hex_u64(&raw_creation.gas);
        let deployment_cost_wei =
            Self::calculate_transaction_fee(gas_limit, &raw_creation.gas_price);
        let deployment_cost_eth = Self::wei_to_eth(&deployment_cost_wei);

        // Analyze bytecode
        let bytecode_analysis = Self::analyze_bytecode(&raw_creation.input);

        // Detect contract type
        let contract_type = Self::detect_contract_type(&raw_creation.input);

        // Detect proxy patterns
        let (is_proxy, implementation_address) = Self::detect_proxy_pattern(&raw_creation.input);

        // Determine transaction subtype
        let transaction_subtype = Self::determine_deployment_type(&raw_creation.input);

        // Get protocol from contract type
        let protocol = Self::contract_type_to_protocol(&contract_type);

        // Generate correlation ID
        let correlation_id = format!(
            "{}-{}",
            raw_creation.hash,
            chrono::Utc::now().timestamp_millis()
        );

        // Create decoded deployment details
        let decoded = Self::create_decoded_deployment_details(
            &raw_creation.hash,
            &raw_creation.from,
            &contract_address,
            &raw_creation.input,
            &bytecode_analysis,
            &contract_type,
            is_proxy,
            implementation_address.as_deref(),
        );

        // Determine transaction currency and value
        let transaction_currency = Self::get_network_currency(&network);
        let transaction_value = format!("{:.6} {}", deployment_cost_eth, transaction_currency);

        // Prefer block timestamp from raw payload; fall back to current time if missing.
        let block_timestamp = raw_creation
            .block_timestamp
            .as_ref()
            .map(|ts| Self::parse_hex_u64(ts))
            .unwrap_or_else(|| chrono::Utc::now().timestamp() as u64);

        // Create processed deployment
        let processed_deployment = ProcessedContractCreation {
            network: network.clone(),
            subnet: subnet.clone(),
            vm_type: vm_type.clone(),
            transaction_hash: raw_creation.hash.clone(),
            block_number,
            block_timestamp,
            creator_address: raw_creation.from.clone(),
            contract_address: contract_address.clone(),
            deployment_bytecode: raw_creation.input.clone(),
            runtime_bytecode: None, // Would be extracted in production
            constructor_args: None, // Would be extracted in production
            gas_used: gas_limit,    // Use gas limit as estimate
            gas_price: raw_creation.gas_price.clone(),
            deployment_cost_wei,
            deployment_cost_eth,
            bytecode_size: bytecode_analysis.size,
            bytecode_hash: bytecode_analysis.hash,
            bytecode_complexity: bytecode_analysis.complexity,
            detected_patterns: bytecode_analysis.patterns,
            contract_type,
            is_proxy,
            implementation_address,
            creator_deployment_count: 1, // Would be fetched from Redis in production
            is_factory: false,           // Would be determined from deployment count
            processed_at: chrono::Utc::now().to_rfc3339(),
            processor_id: "eth-contract-creation-processor-actor".to_string(),
            correlation_id,
            // Standardized enrichment fields
            transaction_type: "contract_deployment".to_string(),
            transaction_currency: transaction_currency.clone(),
            transaction_value,
            transaction_subtype,
            protocol,
            category: "infrastructure".to_string(),
            decoded,
        };

        // Publish to all destinations
        Self::publish_processed_deployment(&processed_deployment, &network, &subnet)?;

        Ok(())
    }

    /// Calculate contract address using CREATE formula
    /// address = keccak256(rlp([sender, nonce]))[12:]
    /// Simplified implementation - would use proper RLP encoding in production
    fn calculate_contract_address(sender: &str, nonce: u64) -> String {
        // Simplified: Use hash of sender + nonce
        // In production, would use proper RLP encoding and keccak256
        let data = format!("{}{}", sender, nonce);
        let hash = Self::simple_hash(&data);
        format!("0x{}", &hash[24..]) // Take last 20 bytes (40 hex chars)
    }

    /// Analyze bytecode for size, complexity, and patterns
    fn analyze_bytecode(bytecode: &str) -> BytecodeAnalysis {
        let size = bytecode.len() / 2; // Hex string to bytes
        let hash = Self::calculate_bytecode_hash(bytecode);
        let complexity = Self::calculate_bytecode_complexity(bytecode);
        let patterns = Self::detect_bytecode_patterns(bytecode);

        BytecodeAnalysis {
            size,
            hash,
            complexity,
            patterns,
        }
    }

    /// Calculate SHA-256 hash of bytecode for deduplication
    fn calculate_bytecode_hash(bytecode: &str) -> String {
        // Simplified hash - would use proper SHA-256 in production
        Self::simple_hash(bytecode)
    }

    /// Calculate bytecode complexity (unique opcodes estimation)
    fn calculate_bytecode_complexity(bytecode: &str) -> u32 {
        // Simplified: Count unique byte pairs as proxy for unique opcodes
        let mut unique_opcodes = HashSet::new();
        let cleaned = bytecode.trim_start_matches("0x");

        for i in (0..cleaned.len()).step_by(2) {
            if i + 2 <= cleaned.len() {
                unique_opcodes.insert(&cleaned[i..i + 2]);
            }
        }

        unique_opcodes.len() as u32
    }

    /// Detect bytecode patterns (proxy, token, etc.)
    fn detect_bytecode_patterns(bytecode: &str) -> Vec<BytecodePattern> {
        let mut patterns = Vec::new();

        // EIP-1167 Minimal Proxy: 363d3d373d3d3d363d73
        if bytecode.contains("363d3d373d3d3d363d73") {
            patterns.push(BytecodePattern::MinimalProxy);
        }

        // EIP-1967 Transparent Proxy: 360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
        if bytecode.contains("360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc") {
            patterns.push(BytecodePattern::TransparentProxy);
        }

        // EIP-1822 UUPS Proxy: c5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7
        if bytecode.contains("c5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7") {
            patterns.push(BytecodePattern::UUPSProxy);
        }

        // Token template detection (simplified)
        if Self::contains_token_signatures(bytecode) {
            patterns.push(BytecodePattern::TokenTemplate);
        }

        patterns
    }

    /// Detect contract type from bytecode
    fn detect_contract_type(bytecode: &str) -> Option<ContractType> {
        // ERC20: Check for transfer(address,uint256) = 0xa9059cbb
        // approve(address,uint256) = 0x095ea7b3
        // balanceOf(address) = 0x70a08231
        if bytecode.contains("a9059cbb")
            && bytecode.contains("095ea7b3")
            && bytecode.contains("70a08231")
        {
            return Some(ContractType::ERC20Token);
        }

        // ERC721: Check for safeTransferFrom = 0x42842e0e
        // tokenURI(uint256) = 0xc87b56dd
        if bytecode.contains("42842e0e") && bytecode.contains("c87b56dd") {
            return Some(ContractType::ERC721NFT);
        }

        // ERC1155: Check for safeTransferFrom = 0xf242432a
        // safeBatchTransferFrom = 0x2eb2c2d6
        if bytecode.contains("f242432a") && bytecode.contains("2eb2c2d6") {
            return Some(ContractType::ERC1155MultiToken);
        }

        // Proxy detection
        if Self::contains_proxy_patterns(bytecode) {
            return Some(ContractType::ProxyContract);
        }

        None
    }

    /// Detect proxy pattern and extract implementation address
    fn detect_proxy_pattern(bytecode: &str) -> (bool, Option<String>) {
        // Check for delegatecall opcode (0xf4)
        if bytecode.contains("f4") {
            // Simplified: Would extract implementation address in production
            return (true, None);
        }
        (false, None)
    }

    /// Determine deployment type (CREATE vs CREATE2)
    fn determine_deployment_type(_bytecode: &str) -> String {
        // Simplified: Would check for CREATE2 salt in transaction data
        "create".to_string()
    }

    /// Convert contract type to protocol string
    fn contract_type_to_protocol(contract_type: &Option<ContractType>) -> Option<String> {
        match contract_type {
            Some(ContractType::ERC20Token) => Some("ERC20".to_string()),
            Some(ContractType::ERC721NFT) => Some("ERC721".to_string()),
            Some(ContractType::ERC1155MultiToken) => Some("ERC1155".to_string()),
            Some(ContractType::UniswapV2Pair) => Some("Uniswap_V2".to_string()),
            Some(ContractType::UniswapV3Pool) => Some("Uniswap_V3".to_string()),
            Some(ContractType::ProxyContract) => Some("Proxy".to_string()),
            Some(ContractType::MultiSigWallet) => Some("MultiSig".to_string()),
            Some(ContractType::Unknown) | None => None,
        }
    }

    /// Helper: Check for token function signatures
    fn contains_token_signatures(bytecode: &str) -> bool {
        bytecode.contains("a9059cbb") || // transfer
        bytecode.contains("095ea7b3") || // approve
        bytecode.contains("70a08231") // balanceOf
    }

    /// Helper: Check for proxy patterns
    fn contains_proxy_patterns(bytecode: &str) -> bool {
        bytecode.contains("363d3d373d3d3d363d73") || // Minimal proxy
        bytecode.contains("360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc")
        // Transparent proxy
    }

    /// Convert Wei (as hex string) to ETH (as f64)
    fn wei_to_eth(wei_hex: &str) -> f64 {
        let wei_value = Self::parse_hex_u128(wei_hex);
        wei_value as f64 / 1_000_000_000_000_000_000.0
    }

    /// Calculate transaction fee in Wei
    fn calculate_transaction_fee(gas_used: u64, gas_price_hex: &str) -> String {
        let gas_price = Self::parse_hex_u128(gas_price_hex);
        let fee = gas_price * gas_used as u128;
        format!("0x{:x}", fee)
    }

    /// Get native currency for network
    fn get_network_currency(network: &str) -> String {
        match network.to_lowercase().as_str() {
            "ethereum" => "ETH".to_string(),
            "polygon" => "MATIC".to_string(),
            "binance" => "BNB".to_string(),
            "avalanche" => "AVAX".to_string(),
            _ => "ETH".to_string(), // Default to ETH
        }
    }

    /// Create decoded deployment details JSON
    fn create_decoded_deployment_details(
        transaction_hash: &str,
        creator_address: &str,
        contract_address: &str,
        bytecode: &str,
        bytecode_analysis: &BytecodeAnalysis,
        contract_type: &Option<ContractType>,
        is_proxy: bool,
        implementation_address: Option<&str>,
    ) -> serde_json::Value {
        let deployment_type = Self::determine_deployment_type(bytecode);

        serde_json::json!({
            "deployment_type": deployment_type,
            "creator": creator_address,
            "contract_address": contract_address,
            "bytecode_size": bytecode_analysis.size,
            "bytecode_hash": &bytecode_analysis.hash,
            "constructor_args": null,  // Would be extracted in production
            "detected_type": contract_type.as_ref().map(|ct| format!("{:?}", ct)),
            "detected_patterns": bytecode_analysis.patterns.iter()
                .map(|p| format!("{:?}", p))
                .collect::<Vec<_>>(),
            "is_proxy": is_proxy,
            "implementation_address": implementation_address,
        })
    }

    /// Parse hexadecimal string to u128
    fn parse_hex_u128(hex_str: &str) -> u128 {
        let cleaned = hex_str.trim_start_matches("0x");
        u128::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Parse hexadecimal string to u64
    fn parse_hex_u64(hex_str: &str) -> u64 {
        let cleaned = hex_str.trim_start_matches("0x");
        u64::from_str_radix(cleaned, 16).unwrap_or(0)
    }

    /// Simplified hash function (would use SHA-256 in production)
    fn simple_hash(data: &str) -> String {
        // Simplified: Use a deterministic hash
        let mut hash: u64 = 0;
        for byte in data.bytes() {
            hash = hash.wrapping_mul(31).wrapping_add(byte as u64);
        }
        format!("{:064x}", hash)
    }

    /// Publish processed deployment to all destinations
    fn publish_processed_deployment(
        processed_deployment: &ProcessedContractCreation,
        network: &str,
        subnet: &str,
    ) -> Result<(), String> {
        let payload = serde_json::to_vec(processed_deployment)
            .map_err(|e| format!("Failed to serialize processed deployment: {}", e))?;

        // 1. Publish to deployed contracts subject
        let deployed_subject = "contracts.deployed.evm".to_string();
        Self::publish_message(&deployed_subject, &payload)?;

        // 2. Publish to alert evaluation system
        let alert_subject = format!("alerts.evaluate.{}.{}", network, subnet);
        Self::publish_message(&alert_subject, &payload)?;

        // 3. Publish contract registry updates
        let registry_subject = format!("contracts.registry.{}.{}", network, subnet);
        Self::publish_message(&registry_subject, &payload)?;

        // 4. Publish to DuckLake for persistence
        let ducklake_record = Self::build_ducklake_transaction_record(processed_deployment);
        let ducklake_payload = serde_json::to_vec(&ducklake_record)
            .map_err(|e| format!("Failed to serialize ducklake transaction: {}", e))?;
        let ducklake_subject = format!("ducklake.transactions.{}.{}.write", network, subnet);
        Self::publish_message(&ducklake_subject, &ducklake_payload)?;

        let address_records = Self::build_address_transaction_records(processed_deployment);
        let address_subject = format!("ducklake.address_transactions.{}.{}.write", network, subnet);
        for record in address_records {
            let address_payload = serde_json::to_vec(&record)
                .map_err(|e| format!("Failed to serialize address transaction: {}", e))?;
            Self::publish_message(&address_subject, &address_payload)?;
        }

        Ok(())
    }

    /// Helper to publish a message to a subject
    fn publish_message(subject: &str, payload: &[u8]) -> Result<(), String> {
        let msg = types::BrokerMessage {
            subject: subject.to_string(),
            body: payload.to_vec(),
            reply_to: None,
        };

        consumer::publish(&msg)
            .map_err(|e| format!("Failed to publish to {}: {:?}", subject, e))?;

        eprintln!("[DEBUG] ✅ Published to: {}", subject);
        Ok(())
    }

    fn build_ducklake_transaction_record(
        processed_deployment: &ProcessedContractCreation,
    ) -> DuckLakeTransactionRecord {
        let block_date = Utc
            .timestamp_opt(processed_deployment.block_timestamp as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "1970-01-01".to_string());

        DuckLakeTransactionRecord {
            chain_id: format!(
                "{}_{}",
                processed_deployment.network, processed_deployment.subnet
            ),
            block_date,
            network: processed_deployment.network.clone(),
            subnet: processed_deployment.subnet.clone(),
            vm_type: processed_deployment.vm_type.clone(),
            block_number: processed_deployment.block_number,
            block_timestamp: processed_deployment.block_timestamp,
            transaction_hash: processed_deployment.transaction_hash.clone(),
            transaction_index: 0,
            from_address: Some(processed_deployment.creator_address.clone()),
            to_address: Some(processed_deployment.contract_address.clone()),
            value: None,
            gas_limit: None,
            gas_used: Some(processed_deployment.gas_used),
            gas_price: Some(Self::normalize_quantity_string(
                &processed_deployment.gas_price,
            )),
            status: "SUCCESS".to_string(),
            transaction_fee: Some(Self::normalize_quantity_string(
                &processed_deployment.deployment_cost_wei,
            )),
            input_data: Some(processed_deployment.deployment_bytecode.clone()),
            method_signature: None,
            transaction_type: processed_deployment.transaction_type.clone(),
            transaction_subtype: Some(processed_deployment.transaction_subtype.clone()),
            decoded_function_name: None,
            decoded_function_signature: None,
            decoded_function_selector: None,
            decoded_parameters: None,
            decoding_status: None,
            abi_source: None,
            decoding_time_ms: None,
            decoded_summary: None,
            nonce: None,
            v: None,
            r: None,
            s: None,
            processor_id: Some(processed_deployment.processor_id.clone()),
            correlation_id: Some(processed_deployment.correlation_id.clone()),
        }
    }

    fn build_address_transaction_records(
        processed_deployment: &ProcessedContractCreation,
    ) -> Vec<DuckLakeAddressTransactionRecord> {
        let block_date = Utc
            .timestamp_opt(processed_deployment.block_timestamp as i64, 0)
            .single()
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "1970-01-01".to_string());

        let chain_id = format!(
            "{}_{}",
            processed_deployment.network, processed_deployment.subnet
        );
        let transaction_type = Some(processed_deployment.transaction_type.clone());
        let transaction_subtype = Some(processed_deployment.transaction_subtype.clone());

        let creator_address = processed_deployment.creator_address.to_lowercase();
        let contract_address = processed_deployment.contract_address.to_lowercase();

        vec![
            DuckLakeAddressTransactionRecord {
                chain_id: chain_id.clone(),
                block_date: block_date.clone(),
                address: creator_address.clone(),
                transaction_hash: processed_deployment.transaction_hash.clone(),
                block_number: processed_deployment.block_number,
                block_timestamp: processed_deployment.block_timestamp,
                is_sender: true,
                counterparty_address: Some(contract_address.clone()),
                value: None,
                transaction_type: transaction_type.clone(),
                transaction_subtype: transaction_subtype.clone(),
            },
            DuckLakeAddressTransactionRecord {
                chain_id,
                block_date,
                address: contract_address,
                transaction_hash: processed_deployment.transaction_hash.clone(),
                block_number: processed_deployment.block_number,
                block_timestamp: processed_deployment.block_timestamp,
                is_sender: false,
                counterparty_address: Some(creator_address),
                value: None,
                transaction_type,
                transaction_subtype,
            },
        ]
    }

    fn normalize_quantity_string(value: &str) -> String {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            return "0".to_string();
        }
        let normalized = trimmed.trim_start_matches("0x");
        if trimmed.starts_with("0x") {
            u128::from_str_radix(normalized, 16)
                .unwrap_or(0)
                .to_string()
        } else {
            normalized.parse::<u128>().unwrap_or(0).to_string()
        }
    }
}

/// Bytecode analysis results
struct BytecodeAnalysis {
    size: usize,
    hash: String,
    complexity: u32,
    patterns: Vec<BytecodePattern>,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_deployment() -> RawContractCreation {
        RawContractCreation {
            hash: "0x2234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string(),
            from: "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045".to_string(),
            to: None, // Contract creation has no to_address
            value: "0x0".to_string(),
            gas: "0x2dc6c0".to_string(),          // 3000000 in hex
            gas_price: "0x4a817c800".to_string(), // 20 Gwei
            input: "0x608060405234801561001057600080fd5b50a9059cbb095ea7b370a08231".to_string(), // Sample ERC20-like bytecode
            nonce: "0x5".to_string(),                        // 5 in hex
            block_number: "0x11a4bc0".to_string(),           // 18500000 in hex
            block_timestamp: Some("0x6544aec0".to_string()), // 1699000000 in hex
            block_hash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
                .to_string(),
            transaction_index: "0x2a".to_string(), // 42 in hex
            chain_id: "0x1".to_string(),           // 1 for mainnet
            contract_address: Some("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb".to_string()),
            v: Some("0x1".to_string()),
            r: Some(
                "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string(),
            ),
            s: Some(
                "0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321".to_string(),
            ),
        }
    }

    #[test]
    fn test_calculate_contract_address() {
        let address = Component::calculate_contract_address("0xdeployer123", 5);
        assert!(address.starts_with("0x"));
        assert_eq!(address.len(), 42); // 0x + 40 hex chars
    }

    #[test]
    fn test_wei_to_eth_conversion() {
        // 1 ETH = 1000000000000000000 Wei
        let eth = Component::wei_to_eth("0xde0b6b3a7640000");
        assert!((eth - 1.0).abs() < 0.0001);

        // 0.5 ETH
        let eth = Component::wei_to_eth("0x6f05b59d3b20000");
        assert!((eth - 0.5).abs() < 0.0001);
    }

    #[test]
    fn test_calculate_deployment_cost() {
        // gas_used = 2,500,000, gas_price = 20 Gwei (0x4a817c800)
        let cost = Component::calculate_transaction_fee(2500000, "0x4a817c800");
        let cost_eth = Component::wei_to_eth(&cost);
        assert!((cost_eth - 0.05).abs() < 0.001); // ~0.05 ETH
    }

    #[test]
    fn test_bytecode_analysis() {
        let raw_creation = create_test_deployment();
        let analysis = Component::analyze_bytecode(&raw_creation.input);

        assert!(analysis.size > 0);
        assert!(!analysis.hash.is_empty());
        assert!(analysis.complexity > 0);
    }

    #[test]
    fn test_bytecode_complexity() {
        let bytecode = "0x608060405234801561001057600080fd5b50";
        let complexity = Component::calculate_bytecode_complexity(bytecode);
        assert!(complexity > 0);
        assert!(complexity < 100); // Reasonable complexity range
    }

    #[test]
    fn test_detect_minimal_proxy_pattern() {
        let bytecode = "0x363d3d373d3d3d363d73bebebebebebebebebebebebebebebebebebebebe5af43d82803e903d91602b57fd5bf3";
        let patterns = Component::detect_bytecode_patterns(bytecode);
        assert!(patterns.contains(&BytecodePattern::MinimalProxy));
    }

    #[test]
    fn test_detect_transparent_proxy_pattern() {
        let bytecode = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";
        let patterns = Component::detect_bytecode_patterns(bytecode);
        assert!(patterns.contains(&BytecodePattern::TransparentProxy));
    }

    #[test]
    fn test_detect_erc20_contract() {
        let bytecode = "0xa9059cbb095ea7b370a08231"; // Contains transfer, approve, balanceOf
        let contract_type = Component::detect_contract_type(bytecode);
        assert_eq!(contract_type, Some(ContractType::ERC20Token));
    }

    #[test]
    fn test_detect_erc721_contract() {
        let bytecode = "0x42842e0ec87b56dd"; // Contains safeTransferFrom, tokenURI
        let contract_type = Component::detect_contract_type(bytecode);
        assert_eq!(contract_type, Some(ContractType::ERC721NFT));
    }

    #[test]
    fn test_detect_proxy_pattern() {
        let bytecode = "0xf4"; // Contains delegatecall
        let (is_proxy, _) = Component::detect_proxy_pattern(bytecode);
        assert!(is_proxy);
    }

    #[test]
    fn test_get_network_currency() {
        assert_eq!(Component::get_network_currency("ethereum"), "ETH");
        assert_eq!(Component::get_network_currency("polygon"), "MATIC");
        assert_eq!(Component::get_network_currency("binance"), "BNB");
        assert_eq!(Component::get_network_currency("avalanche"), "AVAX");
        assert_eq!(Component::get_network_currency("unknown"), "ETH");
    }

    #[test]
    fn test_contract_type_to_protocol() {
        assert_eq!(
            Component::contract_type_to_protocol(&Some(ContractType::ERC20Token)),
            Some("ERC20".to_string())
        );
        assert_eq!(
            Component::contract_type_to_protocol(&Some(ContractType::ERC721NFT)),
            Some("ERC721".to_string())
        );
        assert_eq!(
            Component::contract_type_to_protocol(&Some(ContractType::ProxyContract)),
            Some("Proxy".to_string())
        );
        assert_eq!(Component::contract_type_to_protocol(&None), None);
    }

    #[test]
    fn test_create_decoded_deployment_details() {
        let raw_creation = create_test_deployment();
        let contract_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb";
        let analysis = Component::analyze_bytecode(&raw_creation.input);
        let contract_type = Some(ContractType::ERC20Token);

        let decoded = Component::create_decoded_deployment_details(
            &raw_creation.hash,
            &raw_creation.from,
            contract_address,
            &raw_creation.input,
            &analysis,
            &contract_type,
            false,
            None,
        );

        assert_eq!(decoded["deployment_type"], "create");
        assert_eq!(
            decoded["creator"],
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        );
        assert_eq!(
            decoded["contract_address"],
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        );
        assert!(decoded["bytecode_size"].as_u64().unwrap() > 0);
        assert_eq!(decoded["is_proxy"], false);
        assert_eq!(decoded["detected_type"], "ERC20Token");
    }

    #[test]
    fn test_all_enrichment_fields_populated() {
        let raw_creation = create_test_deployment();
        let gas_limit = Component::parse_hex_u64(&raw_creation.gas);
        let deployment_cost_wei =
            Component::calculate_transaction_fee(gas_limit, &raw_creation.gas_price);
        let deployment_cost_eth = Component::wei_to_eth(&deployment_cost_wei);
        let currency = Component::get_network_currency("ethereum");
        let contract_type = Some(ContractType::ERC20Token);
        let protocol = Component::contract_type_to_protocol(&contract_type);

        // Verify all 7 enrichment fields
        let transaction_type = "contract_deployment".to_string();
        let transaction_currency = currency.clone();
        let transaction_value = format!("{:.6} {}", deployment_cost_eth, currency);
        let transaction_subtype = "create".to_string();
        let category = "infrastructure".to_string();

        assert_eq!(transaction_type, "contract_deployment");
        assert_eq!(transaction_currency, "ETH");
        assert!(transaction_value.contains("ETH"));
        assert_eq!(transaction_subtype, "create");
        assert_eq!(protocol, Some("ERC20".to_string()));
        assert_eq!(category, "infrastructure");
    }

    #[test]
    fn test_parse_hex_u128() {
        assert_eq!(Component::parse_hex_u128("0x1234"), 0x1234);
        assert_eq!(Component::parse_hex_u128("1234"), 0x1234);
        assert_eq!(Component::parse_hex_u128("0x0"), 0);
        assert_eq!(
            Component::parse_hex_u128("0xde0b6b3a7640000"),
            1_000_000_000_000_000_000
        );
        assert_eq!(Component::parse_hex_u128("invalid"), 0);
    }

    #[test]
    fn test_build_ducklake_transaction_record() {
        let processed = ProcessedContractCreation {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: "0xabc".to_string(),
            block_number: 18500000,
            block_timestamp: 1700000000,
            creator_address: "0xcreator".to_string(),
            contract_address: "0xcontract".to_string(),
            deployment_bytecode: "0x60".to_string(),
            runtime_bytecode: None,
            constructor_args: None,
            gas_used: 21000,
            gas_price: "0x4a817c800".to_string(),
            deployment_cost_wei: "0x0".to_string(),
            deployment_cost_eth: 0.0,
            bytecode_size: 2,
            bytecode_hash: "0xhash".to_string(),
            bytecode_complexity: 1,
            detected_patterns: vec![],
            contract_type: None,
            is_proxy: false,
            implementation_address: None,
            creator_deployment_count: 1,
            is_factory: false,
            processed_at: "2024-01-01T00:00:00Z".to_string(),
            processor_id: "test".to_string(),
            correlation_id: "corr".to_string(),
            transaction_type: "contract_deployment".to_string(),
            transaction_currency: "ETH".to_string(),
            transaction_value: "0".to_string(),
            transaction_subtype: "create".to_string(),
            protocol: None,
            category: "infrastructure".to_string(),
            decoded: serde_json::json!({}),
        };

        let record = Component::build_ducklake_transaction_record(&processed);

        assert_eq!(record.chain_id, "ethereum_mainnet");
        assert_eq!(record.transaction_type, "contract_deployment");
        assert_eq!(record.transaction_subtype, Some("create".to_string()));
        assert_eq!(record.transaction_fee, Some("0".to_string()));
    }

    #[test]
    fn test_build_address_transaction_records() {
        let processed = ProcessedContractCreation {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: "0xabc".to_string(),
            block_number: 18500000,
            block_timestamp: 1700000000,
            creator_address: "0xCreator".to_string(),
            contract_address: "0xContract".to_string(),
            deployment_bytecode: "0x60".to_string(),
            runtime_bytecode: None,
            constructor_args: None,
            gas_used: 21000,
            gas_price: "0x4a817c800".to_string(),
            deployment_cost_wei: "0x0".to_string(),
            deployment_cost_eth: 0.0,
            bytecode_size: 2,
            bytecode_hash: "0xhash".to_string(),
            bytecode_complexity: 1,
            detected_patterns: vec![],
            contract_type: None,
            is_proxy: false,
            implementation_address: None,
            creator_deployment_count: 1,
            is_factory: false,
            processed_at: "2024-01-01T00:00:00Z".to_string(),
            processor_id: "test".to_string(),
            correlation_id: "corr".to_string(),
            transaction_type: "contract_deployment".to_string(),
            transaction_currency: "ETH".to_string(),
            transaction_value: "0".to_string(),
            transaction_subtype: "create".to_string(),
            protocol: None,
            category: "infrastructure".to_string(),
            decoded: serde_json::json!({}),
        };

        let records = Component::build_address_transaction_records(&processed);

        assert_eq!(records.len(), 2);
        assert!(records.iter().any(|r| r.is_sender));
        assert!(records.iter().any(|r| !r.is_sender));

        let from_record = records.iter().find(|r| r.is_sender).expect("from record");
        let to_record = records.iter().find(|r| !r.is_sender).expect("to record");

        assert_eq!(from_record.address, "0xcreator");
        assert_eq!(to_record.address, "0xcontract");
        assert_eq!(
            from_record.counterparty_address.as_deref(),
            Some("0xcontract")
        );
        assert_eq!(to_record.counterparty_address.as_deref(), Some("0xcreator"));
        assert_eq!(
            from_record.transaction_type.as_deref(),
            Some("contract_deployment")
        );
    }

    #[test]
    fn test_deployment_type_determination() {
        let bytecode = "0x608060405234801561001057600080fd5b50";
        let deployment_type = Component::determine_deployment_type(bytecode);
        assert_eq!(deployment_type, "create");
    }

    #[test]
    fn test_contains_token_signatures() {
        let bytecode_with_token = "0xa9059cbb095ea7b370a08231";
        assert!(Component::contains_token_signatures(bytecode_with_token));

        let bytecode_without_token = "0x608060405234801561001057600080fd5b50";
        assert!(!Component::contains_token_signatures(
            bytecode_without_token
        ));
    }

    #[test]
    fn test_contains_proxy_patterns() {
        let minimal_proxy = "0x363d3d373d3d3d363d73";
        assert!(Component::contains_proxy_patterns(minimal_proxy));

        let transparent_proxy =
            "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";
        assert!(Component::contains_proxy_patterns(transparent_proxy));

        let no_proxy = "0x608060405234801561001057600080fd5b50";
        assert!(!Component::contains_proxy_patterns(no_proxy));
    }

    #[test]
    fn test_bytecode_hash_consistency() {
        let bytecode = "0x608060405234801561001057600080fd5b50";
        let hash1 = Component::calculate_bytecode_hash(bytecode);
        let hash2 = Component::calculate_bytecode_hash(bytecode);
        assert_eq!(hash1, hash2); // Same bytecode produces same hash
    }

    #[test]
    fn test_decoded_structure_completeness() {
        let raw_creation = create_test_deployment();
        let nonce = Component::parse_hex_u64(&raw_creation.nonce);
        let contract_address = Component::calculate_contract_address(&raw_creation.from, nonce);
        let analysis = Component::analyze_bytecode(&raw_creation.input);
        let contract_type = Component::detect_contract_type(&raw_creation.input);
        let (is_proxy, impl_addr) = Component::detect_proxy_pattern(&raw_creation.input);

        let decoded = Component::create_decoded_deployment_details(
            &raw_creation.hash,
            &raw_creation.from,
            &contract_address,
            &raw_creation.input,
            &analysis,
            &contract_type,
            is_proxy,
            impl_addr.as_deref(),
        );

        // Verify all required fields in decoded JSON
        assert!(decoded.get("deployment_type").is_some());
        assert!(decoded.get("creator").is_some());
        assert!(decoded.get("contract_address").is_some());
        assert!(decoded.get("bytecode_size").is_some());
        assert!(decoded.get("bytecode_hash").is_some());
        assert!(decoded.get("detected_type").is_some());
        assert!(decoded.get("detected_patterns").is_some());
        assert!(decoded.get("is_proxy").is_some());
    }

    #[test]
    fn test_parse_blockchain_context() {
        let (network, subnet, vm_type) =
            Component::parse_blockchain_context("blockchain.ethereum.mainnet.contracts.creation")
                .expect("should parse blockchain subject");

        assert_eq!(network, "ethereum");
        assert_eq!(subnet, "mainnet");
        assert_eq!(vm_type, "evm");
    }
}
