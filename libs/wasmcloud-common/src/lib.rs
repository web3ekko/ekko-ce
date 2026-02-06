use serde::{Deserialize, Serialize};

/// Initialize the WasmCloud common library
pub fn init() {
    // Initialize logging or other common setup
    eprintln!("WasmCloud common initialized");
}

/// Common message types for WasmCloud actors
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub id: String,
    pub subject: String,
    pub payload: Vec<u8>,
    pub timestamp: u64,
}

/// Common response types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Response<T> {
    pub success: bool,
    pub data: Option<T>,
    pub error: Option<String>,
    pub timestamp: u64,
}

impl<T> Response<T> {
    pub fn success(data: T) -> Self {
        Self {
            success: true,
            data: Some(data),
            error: None,
            timestamp: chrono::Utc::now().timestamp() as u64,
        }
    }

    pub fn error(error: String) -> Self {
        Self {
            success: false,
            data: None,
            error: Some(error),
            timestamp: chrono::Utc::now().timestamp() as u64,
        }
    }
}

/// Utility functions for subject parsing
pub fn parse_subject(subject: &str) -> Vec<String> {
    subject.split('.').map(|s| s.to_string()).collect()
}

/// Extract chain from subject pattern like "blockchain.{chain}.raw"
pub fn extract_chain_from_subject(subject: &str) -> Option<String> {
    let parts = parse_subject(subject);
    if parts.len() >= 3 && parts[0] == "blockchain" {
        Some(parts[1].clone())
    } else {
        None
    }
}

/// Build a subject from components
pub fn build_subject(components: &[&str]) -> String {
    components.join(".")
}