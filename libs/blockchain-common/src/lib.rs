use serde::{Deserialize, Serialize};

/// Blockchain transaction with full details
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockchainTransaction {
    pub hash: String,
    pub chain: String,
    pub block_number: u64,
    pub block_hash: Option<String>,
    pub from: Option<String>,
    pub to: Option<String>,
    pub value: Option<String>,
    pub gas_price: Option<String>,
    pub gas_used: Option<u64>,
    pub data: Option<String>,
    pub timestamp: u64,
    pub transaction_index: Option<u64>,
    pub nonce: Option<u64>,
}

/// Supported blockchain networks
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Chain {
    Ethereum,
    BinanceSmartChain,
    Polygon,
    Avalanche,
    Arbitrum,
    Optimism,
    Bitcoin,
    Solana,
}

impl Chain {
    pub fn as_str(&self) -> &str {
        match self {
            Chain::Ethereum => "ethereum",
            Chain::BinanceSmartChain => "bsc",
            Chain::Polygon => "polygon",
            Chain::Avalanche => "avalanche",
            Chain::Arbitrum => "arbitrum",
            Chain::Optimism => "optimism",
            Chain::Bitcoin => "bitcoin",
            Chain::Solana => "solana",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "ethereum" | "eth" => Some(Chain::Ethereum),
            "bsc" | "binance" => Some(Chain::BinanceSmartChain),
            "polygon" | "matic" => Some(Chain::Polygon),
            "avalanche" | "avax" => Some(Chain::Avalanche),
            "arbitrum" | "arb" => Some(Chain::Arbitrum),
            "optimism" | "op" => Some(Chain::Optimism),
            "bitcoin" | "btc" => Some(Chain::Bitcoin),
            "solana" | "sol" => Some(Chain::Solana),
            _ => None,
        }
    }
}

/// Block header information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockHeader {
    pub number: u64,
    pub hash: String,
    pub parent_hash: String,
    pub timestamp: u64,
    pub miner: Option<String>,
    pub difficulty: Option<String>,
    pub gas_limit: Option<u64>,
    pub gas_used: Option<u64>,
    pub transactions_count: u32,
}