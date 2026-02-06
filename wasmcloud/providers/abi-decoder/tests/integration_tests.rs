//! Integration tests for ABI decoder provider
//!
//! These tests use testcontainers to spin up Redis and MinIO instances
//! to validate actual ABI caching, decoding operations, and provider functionality.

use abi_decoder_provider::{AbiDecoderProvider, DecodingStatus, TransactionInput};
use anyhow::Result;
use serial_test::serial;
use std::time::Duration;
use testcontainers::{runners::AsyncRunner, ContainerAsync};
use testcontainers_modules::{minio::MinIO, redis::Redis};
use tokio::time::sleep;

/// Test environment with Redis and MinIO containers
struct TestEnvironment {
    _redis: ContainerAsync<Redis>,
    _minio: ContainerAsync<MinIO>,
    redis_url: String,
    minio_endpoint: String,
    provider: AbiDecoderProvider,
}

impl TestEnvironment {
    /// Set up test environment with Redis and MinIO containers
    async fn new() -> Result<Self> {
        // Start Redis container
        let redis = Redis::default().start().await?;
        let redis_port = redis.get_host_port_ipv4(6379).await?;
        let redis_url = format!("redis://127.0.0.1:{}", redis_port);

        // Start MinIO container
        let minio = MinIO::default().start().await?;
        let minio_port = minio.get_host_port_ipv4(9000).await?;
        let minio_endpoint = format!("http://127.0.0.1:{}", minio_port);

        // Wait for containers to be ready
        sleep(Duration::from_secs(3)).await;

        // Set environment variables for provider
        std::env::set_var("ABI_DECODER_REDIS_URL", &redis_url);
        std::env::set_var("ABI_DECODER_S3_ENDPOINT", &minio_endpoint);
        std::env::set_var("ABI_DECODER_S3_ACCESS_KEY_ID", "minioadmin");
        std::env::set_var("ABI_DECODER_S3_SECRET_ACCESS_KEY", "minioadmin");
        std::env::set_var("ABI_DECODER_S3_BUCKET", "test-bucket");
        std::env::set_var("ABI_DECODER_HOT_CACHE_SIZE", "100");

        // Create provider
        let provider = AbiDecoderProvider::new().await?;

        println!("🐳 Test environment ready:");
        println!("  Redis: {}", redis_url);
        println!("  MinIO: {}", minio_endpoint);

        Ok(Self {
            _redis: redis,
            _minio: minio,
            redis_url,
            minio_endpoint,
            provider,
        })
    }
}

#[tokio::test]
#[serial]
async fn test_provider_initialization() -> Result<()> {
    let _env = TestEnvironment::new().await?;

    println!("✅ ABI decoder provider initialized successfully");
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_native_transfer_detection() -> Result<()> {
    let env = TestEnvironment::new().await?;

    let native_transfer = TransactionInput {
        to_address: "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6".to_string(),
        input_data: "0x".to_string(),
        network: "ethereum".to_string(),
        subnet: "mainnet".to_string(),
        transaction_hash: "0x1234567890abcdef".to_string(),
    };

    let result = env.provider.decode_transaction(native_transfer).await?;

    assert_eq!(result.status, DecodingStatus::NativeTransfer);
    assert!(result.decoded_function.is_none());
    assert!(result.processing_time_ms > 0);

    println!("✅ Native transfer detection works correctly");
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_contract_creation_detection() -> Result<()> {
    let env = TestEnvironment::new().await?;

    let contract_creation = TransactionInput {
        to_address: "".to_string(),
        input_data: "0x608060405234801561001057600080fd5b50".to_string(),
        network: "ethereum".to_string(),
        subnet: "mainnet".to_string(),
        transaction_hash: "0xabcdef1234567890".to_string(),
    };

    let result = env.provider.decode_transaction(contract_creation).await?;

    assert_eq!(result.status, DecodingStatus::ContractCreation);
    assert!(result.decoded_function.is_none());
    assert!(result.processing_time_ms > 0);

    println!("✅ Contract creation detection works correctly");
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_abi_not_found() -> Result<()> {
    let env = TestEnvironment::new().await?;

    // ERC-20 transfer call without ABI
    let erc20_transfer = TransactionInput {
        to_address: "0xA0b86a33E6441b8C4505E2c4B5b5b5b5b5b5b5b5".to_string(),
        input_data: "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b60000000000000000000000000000000000000000000000000de0b6b3a7640000".to_string(),
        network: "ethereum".to_string(),
        subnet: "mainnet".to_string(),
        transaction_hash: "0xfedcba0987654321".to_string(),
    };

    let result = env.provider.decode_transaction(erc20_transfer).await?;

    assert_eq!(result.status, DecodingStatus::AbiNotFound);
    assert!(result.decoded_function.is_none());
    assert!(result.error_message.is_some());
    assert!(result.processing_time_ms >= 0);

    println!("✅ ABI not found handling works correctly");
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_abi_caching() -> Result<()> {
    let env = TestEnvironment::new().await?;

    // Example ERC-20 ABI (simplified)
    let erc20_abi = r#"[
        {
            "constant": false,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        }
    ]"#;

    let contract_address = "0xA0b86a33E6441b8C4505E2c4B5b5b5b5b5b5b5b5";
    let network = "ethereum";

    // Cache the ABI
    env.provider
        .cache_abi(contract_address, network, erc20_abi, "test")
        .await?;

    // Verify ABI exists
    let has_abi = env.provider.has_abi(contract_address, network).await?;
    assert!(has_abi);

    // Get ABI
    let abi_info = env.provider.get_abi(contract_address, network).await?;
    assert!(abi_info.is_some());

    let abi = abi_info.unwrap();
    assert_eq!(abi.contract_address, contract_address);
    assert_eq!(abi.source, "test");
    assert!(abi.verified);

    println!("✅ ABI caching works correctly");
    Ok(())
}

#[tokio::test]
#[serial]
async fn test_successful_decoding() -> Result<()> {
    let env = TestEnvironment::new().await?;

    // Example ERC-20 ABI with transfer function
    let erc20_abi = r#"[
        {
            "constant": false,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"}
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        }
    ]"#;

    let contract_address = "0xA0b86a33E6441b8C4505E2c4B5b5b5b5b5b5b5b5";
    let network = "ethereum";

    // Cache the ABI first
    env.provider
        .cache_abi(contract_address, network, erc20_abi, "test")
        .await?;

    // ERC-20 transfer transaction
    let transfer_tx = TransactionInput {
        to_address: contract_address.to_string(),
        input_data: "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b60000000000000000000000000000000000000000000000000de0b6b3a7640000".to_string(),
        network: network.to_string(),
        subnet: "mainnet".to_string(),
        transaction_hash: "0xfedcba0987654321".to_string(),
    };

    let result = env.provider.decode_transaction(transfer_tx).await?;

    assert_eq!(result.status, DecodingStatus::Success);
    assert!(result.decoded_function.is_some());
    assert_eq!(result.abi_source, Some("test".to_string()));

    let decoded = result.decoded_function.unwrap();
    assert_eq!(decoded.name, "transfer");
    assert_eq!(decoded.signature, "transfer(address,uint256)");
    assert_eq!(decoded.selector, "0xa9059cbb");
    assert_eq!(decoded.parameters.len(), 2);

    // Check parameters
    assert_eq!(decoded.parameters[0].name, "_to");
    assert_eq!(decoded.parameters[0].param_type, "address");
    assert_eq!(decoded.parameters[1].name, "_value");
    assert_eq!(decoded.parameters[1].param_type, "uint256");

    println!("✅ Successful ABI decoding works correctly");
    println!("  Function: {}", decoded.name);
    println!("  Parameters: {}", decoded.parameters.len());

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_batch_processing() -> Result<()> {
    let env = TestEnvironment::new().await?;

    let batch_inputs = vec![
        TransactionInput {
            to_address: "0x1111111111111111111111111111111111111111".to_string(),
            input_data: "0x".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0x1111".to_string(),
        },
        TransactionInput {
            to_address: "".to_string(),
            input_data: "0x608060405234801561001057600080fd5b50".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0x2222".to_string(),
        },
        TransactionInput {
            to_address: "0x3333333333333333333333333333333333333333".to_string(),
            input_data: "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b60000000000000000000000000000000000000000000000000de0b6b3a7640000".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0x3333".to_string(),
        },
    ];

    let results = env.provider.decode_batch(batch_inputs.clone()).await?;

    assert_eq!(results.len(), 3);
    assert_eq!(results[0].status, DecodingStatus::NativeTransfer);
    assert_eq!(results[1].status, DecodingStatus::ContractCreation);
    assert_eq!(results[2].status, DecodingStatus::AbiNotFound);

    println!("✅ Batch processing works correctly");
    println!("  Processed {} transactions", results.len());

    Ok(())
}

#[tokio::test]
#[serial]
async fn test_cache_statistics() -> Result<()> {
    let env = TestEnvironment::new().await?;

    // Get initial stats
    let initial_stats = env.provider.get_cache_stats().await?;
    assert_eq!(initial_stats.total_decodings, 0);
    assert_eq!(initial_stats.successful_decodings, 0);

    // Perform some operations
    let native_transfer = TransactionInput {
        to_address: "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6".to_string(),
        input_data: "0x".to_string(),
        network: "ethereum".to_string(),
        subnet: "mainnet".to_string(),
        transaction_hash: "0x1234567890abcdef".to_string(),
    };

    let _result = env.provider.decode_transaction(native_transfer).await?;

    // Check updated stats
    let updated_stats = env.provider.get_cache_stats().await?;
    assert_eq!(updated_stats.total_decodings, 1);
    assert!(updated_stats.avg_decoding_time_ms >= 0.0);

    println!("✅ Cache statistics work correctly");
    println!("  Total decodings: {}", updated_stats.total_decodings);
    println!("  Avg time: {:.2}ms", updated_stats.avg_decoding_time_ms);

    Ok(())
}
