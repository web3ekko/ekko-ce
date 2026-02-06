use serde::{Deserialize, Serialize};

/// Common transaction type for all blockchain transactions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub hash: String,
    pub chain: String,
    pub block_number: u64,
    pub from: Option<String>,
    pub to: Option<String>,
    pub value: Option<String>,
    pub data: Option<String>,
    pub timestamp: u64,
}

/// Alert type for monitoring
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Alert {
    pub id: String,
    pub name: String,
    pub description: String,
    pub chain: String,
    pub conditions: Vec<String>,
    pub enabled: bool,
}

/// Result type for operations
pub type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

/// Common error types
#[derive(Debug, Clone)]
pub enum Error {
    ParseError(String),
    NetworkError(String),
    StorageError(String),
    NotFound(String),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::ParseError(msg) => write!(f, "Parse error: {}", msg),
            Error::NetworkError(msg) => write!(f, "Network error: {}", msg),
            Error::StorageError(msg) => write!(f, "Storage error: {}", msg),
            Error::NotFound(msg) => write!(f, "Not found: {}", msg),
        }
    }
}

impl std::error::Error for Error {}