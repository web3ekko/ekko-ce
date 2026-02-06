//! Blockchain Subject Patterns
//!
//! Subject hierarchy for blockchain transaction processing with network/subnet:
//! ```text
//! blockchain.{network}.{subnet}.transactions.raw           # Raw transactions from providers
//! blockchain.{network}.{subnet}.transactions.processed     # Processed transactions
//! blockchain.{network}.{subnet}.transactions.transfers     # Transfer-specific transactions
//! blockchain.{network}.{subnet}.contracts.creation         # Contract deployment events
//! blockchain.{network}.{subnet}.contracts.transactions     # Contract interaction events
//! blockchain.{network}.{subnet}.contracts.decoded          # Decoded contract transactions
//! blockchain.abi.decode.{network}.{subnet}.{request|batch} # ABI decoding requests
//! ```
//!
//! Networks: ethereum, polygon, arbitrum, avalanche, bitcoin, solana, cosmos
//! Subnets: mainnet, sepolia, goerli, mumbai, amoy, devnet, testnet

/// Raw transaction subject - from blockchain providers
///
/// Example: `blockchain.ethereum.mainnet.transactions.raw`
pub fn transactions_raw(network: &str, subnet: &str) -> String {
    format!("blockchain.{}.{}.transactions.raw", network, subnet)
}

/// Processed transaction subject - enriched and filtered
///
/// Example: `blockchain.ethereum.mainnet.transactions.processed`
pub fn transactions_processed(network: &str, subnet: &str) -> String {
    format!("blockchain.{}.{}.transactions.processed", network, subnet)
}

/// Returns true if the subject is a single processed-transactions event subject.
///
/// Canonical event subjects:
/// - `blockchain.{network}.{subnet}.transactions.processed`
pub fn is_transactions_processed_event(subject: &str) -> bool {
    let mut parts = subject.split('.');
    match (
        parts.next(),
        parts.next(),
        parts.next(),
        parts.next(),
        parts.next(),
        parts.next(),
    ) {
        (
            Some("blockchain"),
            Some(network),
            Some(subnet),
            Some("transactions"),
            Some("processed"),
            None,
        ) if network != "*" && network != ">" && subnet != "*" && subnet != ">" => true,
        _ => false,
    }
}

/// Returns true if the subject is a single decoded-contracts event subject.
///
/// Canonical event subjects:
/// - `blockchain.{network}.{subnet}.contracts.decoded`
pub fn is_contracts_decoded_event(subject: &str) -> bool {
    let mut parts = subject.split('.');
    match (
        parts.next(),
        parts.next(),
        parts.next(),
        parts.next(),
        parts.next(),
        parts.next(),
    ) {
        (
            Some("blockchain"),
            Some(network),
            Some(subnet),
            Some("contracts"),
            Some("decoded"),
            None,
        ) if network != "*" && network != ">" && subnet != "*" && subnet != ">" => true,
        _ => false,
    }
}

/// Transfer transaction subject - value transfers
///
/// Example: `blockchain.ethereum.mainnet.transactions.transfers`
pub fn transactions_transfers(network: &str, subnet: &str) -> String {
    format!("blockchain.{}.{}.transactions.transfers", network, subnet)
}

/// Contract creation subject - new contract deployments
///
/// Example: `blockchain.ethereum.mainnet.contracts.creation`
pub fn contracts_creation(network: &str, subnet: &str) -> String {
    format!("blockchain.{}.{}.contracts.creation", network, subnet)
}

/// Contract transaction subject - contract interactions
///
/// Example: `blockchain.ethereum.mainnet.contracts.transactions`
pub fn contracts_transactions(network: &str, subnet: &str) -> String {
    format!("blockchain.{}.{}.contracts.transactions", network, subnet)
}

/// Decoded contract transaction subject - with ABI decoding
///
/// Example: `blockchain.ethereum.mainnet.contracts.decoded`
pub fn contracts_decoded(network: &str, subnet: &str) -> String {
    format!("blockchain.{}.{}.contracts.decoded", network, subnet)
}

/// ABI decode request subject for specific network/subnet
///
/// Example: `blockchain.abi.decode.ethereum.mainnet.request`
pub fn abi_decode_request(network: &str, subnet: &str) -> String {
    format!("blockchain.abi.decode.{}.{}.request", network, subnet)
}

/// ABI decode batch subject for specific network/subnet
///
/// Example: `blockchain.abi.decode.ethereum.mainnet.batch`
pub fn abi_decode_batch(network: &str, subnet: &str) -> String {
    format!("blockchain.abi.decode.{}.{}.batch", network, subnet)
}

/// Generic transaction write subject (for DuckLake writer - uses ducklake patterns)
pub fn transactions_write() -> &'static str {
    "ducklake.transactions.write"
}

// =============================================================================
// Subscription Patterns (Wildcards for handlers)
// =============================================================================

/// Pattern for raw transactions from a specific network (all subnets)
///
/// Example: `blockchain.ethereum.>.transactions.raw`
pub fn pattern_transactions_raw_network(network: &str) -> String {
    format!("blockchain.{}.>.transactions.raw", network)
}

/// Pattern for raw transactions from any network/subnet
pub fn pattern_transactions_raw_all() -> &'static str {
    "blockchain.>.>.transactions.raw"
}

/// Pattern for processed transactions from a specific network (all subnets)
///
/// Example: `blockchain.ethereum.>.transactions.processed`
pub fn pattern_transactions_processed_network(network: &str) -> String {
    format!("blockchain.{}.>.transactions.processed", network)
}

/// Pattern for processed transactions from any network/subnet
pub fn pattern_transactions_processed_all() -> &'static str {
    "blockchain.>.>.transactions.processed"
}

/// Pattern for all contract events from a specific network/subnet
///
/// Example: `blockchain.ethereum.mainnet.contracts.>`
pub fn pattern_contracts_all(network: &str, subnet: &str) -> String {
    format!("blockchain.{}.{}.contracts.>", network, subnet)
}

/// Pattern for all contract events from a specific network (all subnets)
///
/// Example: `blockchain.ethereum.>.contracts.>`
pub fn pattern_contracts_network(network: &str) -> String {
    format!("blockchain.{}.>.contracts.>", network)
}

/// Pattern for all blockchain events (use with caution)
pub fn pattern_blockchain_all() -> &'static str {
    "blockchain.>"
}

/// Pattern for ABI decode requests for a specific network (all subnets)
///
/// Example: `blockchain.abi.decode.ethereum.>.>`
pub fn pattern_abi_decode_network(network: &str) -> String {
    format!("blockchain.abi.decode.{}.>", network)
}

/// Pattern for all ABI decode requests
pub fn pattern_abi_decode_all() -> &'static str {
    "blockchain.abi.decode.>"
}

// =============================================================================
// Constants for common networks and subnets
// =============================================================================

pub mod networks {
    pub const ETHEREUM: &str = "ethereum";
    pub const POLYGON: &str = "polygon";
    pub const ARBITRUM: &str = "arbitrum";
    pub const AVALANCHE: &str = "avalanche";
    pub const BITCOIN: &str = "bitcoin";
    pub const SOLANA: &str = "solana";
    pub const COSMOS: &str = "cosmos";
}

pub mod subnets {
    pub const MAINNET: &str = "mainnet";
    pub const SEPOLIA: &str = "sepolia";
    pub const GOERLI: &str = "goerli";
    pub const MUMBAI: &str = "mumbai";
    pub const AMOY: &str = "amoy";
    pub const DEVNET: &str = "devnet";
    pub const TESTNET: &str = "testnet";
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transactions_raw() {
        assert_eq!(
            transactions_raw("ethereum", "mainnet"),
            "blockchain.ethereum.mainnet.transactions.raw"
        );
        assert_eq!(
            transactions_raw("ethereum", "sepolia"),
            "blockchain.ethereum.sepolia.transactions.raw"
        );
        assert_eq!(
            transactions_raw("bitcoin", "mainnet"),
            "blockchain.bitcoin.mainnet.transactions.raw"
        );
    }

    #[test]
    fn test_transactions_processed() {
        assert_eq!(
            transactions_processed("ethereum", "mainnet"),
            "blockchain.ethereum.mainnet.transactions.processed"
        );
        assert_eq!(
            transactions_processed("polygon", "mumbai"),
            "blockchain.polygon.mumbai.transactions.processed"
        );
    }

    #[test]
    fn test_is_transactions_processed_event() {
        assert!(is_transactions_processed_event(
            "blockchain.ethereum.mainnet.transactions.processed"
        ));
        assert!(is_transactions_processed_event(
            "blockchain.avalanche.fuji.transactions.processed"
        ));

        assert!(!is_transactions_processed_event(
            "blockchain.>.>.transactions.processed"
        ));
        assert!(!is_transactions_processed_event(
            "blockchain.ethereum.mainnet.transactions.raw"
        ));
        assert!(!is_transactions_processed_event(
            "transactions.processed.ethereum.mainnet"
        ));
    }

    #[test]
    fn test_contracts_decoded() {
        assert_eq!(
            contracts_decoded("ethereum", "mainnet"),
            "blockchain.ethereum.mainnet.contracts.decoded"
        );
    }

    #[test]
    fn test_is_contracts_decoded_event() {
        assert!(is_contracts_decoded_event(
            "blockchain.ethereum.mainnet.contracts.decoded"
        ));
        assert!(is_contracts_decoded_event(
            "blockchain.avalanche.fuji.contracts.decoded"
        ));

        assert!(!is_contracts_decoded_event(
            "blockchain.>.>.contracts.decoded"
        ));
        assert!(!is_contracts_decoded_event(
            "blockchain.ethereum.mainnet.contracts.transactions"
        ));
        assert!(!is_contracts_decoded_event(
            "contracts.decoded.ethereum.mainnet"
        ));
    }

    #[test]
    fn test_contracts_creation() {
        assert_eq!(
            contracts_creation("ethereum", "mainnet"),
            "blockchain.ethereum.mainnet.contracts.creation"
        );
    }

    #[test]
    fn test_abi_decode() {
        assert_eq!(
            abi_decode_request("ethereum", "mainnet"),
            "blockchain.abi.decode.ethereum.mainnet.request"
        );
        assert_eq!(
            abi_decode_batch("polygon", "mainnet"),
            "blockchain.abi.decode.polygon.mainnet.batch"
        );
    }

    #[test]
    fn test_patterns() {
        assert_eq!(
            pattern_transactions_raw_network("ethereum"),
            "blockchain.ethereum.>.transactions.raw"
        );
        assert_eq!(
            pattern_transactions_raw_all(),
            "blockchain.>.>.transactions.raw"
        );
        assert_eq!(
            pattern_contracts_all("ethereum", "mainnet"),
            "blockchain.ethereum.mainnet.contracts.>"
        );
    }

    #[test]
    fn test_constants() {
        assert_eq!(networks::ETHEREUM, "ethereum");
        assert_eq!(subnets::MAINNET, "mainnet");
    }
}
