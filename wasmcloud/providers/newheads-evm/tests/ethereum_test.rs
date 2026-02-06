//! Integration tests for Ethereum client
//!
//! These tests verify the Ethereum client can connect to real or mock endpoints

use anyhow::Result;
use newheads_evm_provider::ethereum::EthereumClient;
use newheads_evm_provider::traits::{ChainConfig, ChainType, NatsSubjects, VmType};
use tokio;

/// Test Ethereum client creation and basic functionality
#[tokio::test]
async fn test_ethereum_client_creation() -> Result<()> {
    let config = create_test_ethereum_config();

    // This will fail with the default URLs, but we're testing the structure
    let result = EthereumClient::new(config).await;

    // We expect this to fail since we're using placeholder URLs
    assert!(result.is_err());

    // But the error should be a connection error, not a parsing error
    let error_msg = result.unwrap_err().to_string();
    assert!(
        error_msg.contains("Failed to connect")
            || error_msg.contains("HTTP error")
            || error_msg.contains("connection")
    );

    Ok(())
}

/// Test NATS subject generation
#[tokio::test]
async fn test_nats_subject_generation() {
    let subjects = NatsSubjects::generate("ethereum", "mainnet", &VmType::Evm, "ethereum-mainnet");

    assert_eq!(subjects.newheads_output, "newheads.ethereum.mainnet.evm");
    assert_eq!(subjects.config_input, "config.ethereum-mainnet.input");
    assert_eq!(subjects.status_output, "status.ethereum-mainnet.output");
    assert_eq!(subjects.control_input, "control.ethereum-mainnet.input");
}

/// Test different EVM types
#[tokio::test]
async fn test_evm_type_display() {
    assert_eq!(VmType::Evm.to_string(), "evm");
    assert_eq!(VmType::Utxo.to_string(), "utxo");
    assert_eq!(VmType::Svm.to_string(), "svm");
    assert_eq!(VmType::Wasm.to_string(), "wasm");
    assert_eq!(VmType::Custom("custom".to_string()).to_string(), "custom");
}

/// Test chain configuration validation
#[tokio::test]
async fn test_chain_config_validation() {
    let config = create_test_ethereum_config();

    // Basic validation
    assert!(!config.chain_id.is_empty());
    assert!(!config.rpc_url.is_empty());
    assert!(!config.ws_url.is_empty());
    assert!(config.rpc_url.starts_with("http"));
    assert!(config.ws_url.starts_with("ws"));

    // NATS subjects should be properly formatted
    assert!(config.nats_subjects.newheads_output.contains("newheads."));
    assert!(config.nats_subjects.config_input.contains("config."));
}

/// Test multiple chain configurations
#[tokio::test]
async fn test_multiple_chain_configs() {
    let ethereum_config = create_test_ethereum_config();
    let polygon_config = create_test_polygon_config();

    // Should have different chain IDs
    assert_ne!(ethereum_config.chain_id, polygon_config.chain_id);

    // Should have different NATS subjects
    assert_ne!(
        ethereum_config.nats_subjects.newheads_output,
        polygon_config.nats_subjects.newheads_output
    );

    // Both should be EVM type
    assert_eq!(ethereum_config.vm_type, VmType::Evm);
    assert_eq!(polygon_config.vm_type, VmType::Evm);
}

// Helper functions

fn create_test_ethereum_config() -> ChainConfig {
    let nats_subjects =
        NatsSubjects::generate("ethereum", "mainnet", &VmType::Evm, "ethereum-mainnet");

    ChainConfig {
        chain_id: "ethereum-mainnet".to_string(),
        chain_name: "Ethereum Mainnet".to_string(),
        network: "ethereum".to_string(),
        subnet: "mainnet".to_string(),
        vm_type: VmType::Evm,
        rpc_url: "https://mainnet.infura.io/v3/YOUR_PROJECT_ID".to_string(),
        ws_url: "wss://mainnet.infura.io/ws/v3/YOUR_PROJECT_ID".to_string(),
        chain_type: ChainType::Ethereum,
        network_id: Some(1),
        enabled: false,
        nats_subjects,
    }
}

fn create_test_polygon_config() -> ChainConfig {
    let nats_subjects =
        NatsSubjects::generate("polygon", "mainnet", &VmType::Evm, "polygon-mainnet");

    ChainConfig {
        chain_id: "polygon-mainnet".to_string(),
        chain_name: "Polygon Mainnet".to_string(),
        network: "polygon".to_string(),
        subnet: "mainnet".to_string(),
        vm_type: VmType::Evm,
        rpc_url: "https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID".to_string(),
        ws_url: "wss://polygon-mainnet.infura.io/ws/v3/YOUR_PROJECT_ID".to_string(),
        chain_type: ChainType::Polygon,
        network_id: Some(137),
        enabled: false,
        nats_subjects,
    }
}
