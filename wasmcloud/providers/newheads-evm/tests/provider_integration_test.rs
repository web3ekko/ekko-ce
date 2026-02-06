//! Integration tests for the complete newheads provider
//!
//! Tests the provider with Redis configuration and NATS messaging

use anyhow::Result;
use newheads_evm_provider::{config::ConfigManager, NewheadsProvider};
use redis::AsyncCommands;
use serde_json::json;
use testcontainers::runners::AsyncRunner;
use testcontainers_modules::redis::Redis;

/// Test provider initialization with Redis and mock NATS
#[tokio::test]
async fn test_provider_initialization() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    // Mock NATS URL (will fail to connect, but that's expected in this test)
    let nats_url = "nats://localhost:9999"; // Non-existent port

    // Try to initialize provider
    let result = NewheadsProvider::new(&nats_url, &redis_url).await;

    // Should fail due to NATS connection, but that's expected
    assert!(result.is_err(), "Expected NATS connection to fail");

    let error_msg = result.unwrap_err().to_string();
    assert!(
        error_msg.contains("connection")
            || error_msg.contains("refused")
            || error_msg.contains("timeout"),
        "Expected connection error, got: {}",
        error_msg
    );

    println!("✅ Provider correctly failed to connect to non-existent NATS server");

    Ok(())
}

/// Test provider configuration loading
#[tokio::test]
async fn test_provider_config_loading() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    // Pre-populate Redis with configuration
    let config_manager = newheads_evm_provider::config::ConfigManager::new(&redis_url)?;
    config_manager.initialize_default_configs().await?;

    let configs = config_manager.load_all_configs().await?;
    println!(
        "✅ Pre-populated Redis with {} configurations",
        configs.len()
    );

    // Verify we have the expected chains
    let expected_chains = vec![
        "avalanche-c-chain",
        "avalanche-fuji",
        "ethereum-mainnet",
        "ethereum-goerli",
    ];
    for chain_id in expected_chains {
        assert!(
            configs.contains_key(chain_id),
            "Missing expected chain: {}",
            chain_id
        );
        println!("   ✓ Found chain: {}", chain_id);
    }

    // Test NATS subject structure
    let eth_config = configs.get("ethereum-mainnet").unwrap();
    assert_eq!(
        eth_config.nats_subjects.newheads_output,
        "newheads.ethereum.mainnet.evm"
    );
    assert_eq!(
        eth_config.nats_subjects.config_input,
        "config.ethereum-mainnet.input"
    );

    println!("✅ Configuration loading test completed successfully");

    Ok(())
}

/// Test provider with working NATS connection (if available)
#[tokio::test]
async fn test_provider_with_nats() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    // Initialize Django-format configurations in Redis
    let redis_client = redis::Client::open(redis_url.clone())?;
    let mut conn = redis_client.get_async_connection().await?;

    // Add Django format configurations
    let ethereum_node = json!({
        "chain_id": "ethereum-mainnet",
        "chain_name": "Ethereum Mainnet",
        "network": "ethereum",
        "subnet": "mainnet",
        "vm_type": "EVM",
        "rpc_url": "https://mainnet.infura.io/v3/YOUR_PROJECT_ID",
        "ws_url": "wss://mainnet.infura.io/ws/v3/YOUR_PROJECT_ID",
        "enabled": true,
        "is_primary": true,
        "priority": 1,
        "latency_ms": null,
        "success_rate": null,
        "last_health_check": null,
        "created_at": "2025-01-14T00:00:00Z",
        "updated_at": "2025-01-14T00:00:00Z"
    });

    conn.set::<_, _, ()>(
        "blockchain:nodes:ethereum-mainnet",
        ethereum_node.to_string(),
    )
    .await?;
    println!("✅ Initialized Django-format configurations in Redis");

    // Try to connect to local NATS (if available)
    let nats_url = "nats://localhost:4222";

    match NewheadsProvider::new(&nats_url, &redis_url).await {
        Ok(provider) => {
            println!("✅ Successfully created provider with NATS and Redis");

            // Test that configurations were loaded
            let configs = provider.configs().read().await;
            assert!(!configs.is_empty(), "Configurations should be loaded");

            println!("✅ Provider has {} configurations loaded", configs.len());

            // Test configuration access
            if let Some(eth_config) = configs.get("ethereum-mainnet") {
                println!("✅ Ethereum mainnet config:");
                println!("   Chain Name: {}", eth_config.chain_name);
                println!(
                    "   NATS Subject: {}",
                    eth_config.nats_subjects.newheads_output
                );
                println!("   Enabled: {}", eth_config.enabled);
            }
        }
        Err(e) => {
            println!("⚠️  NATS not available at {}: {}", nats_url, e);
            println!("   This is expected if NATS is not running locally");
            println!("   To test with NATS, start a NATS server: `nats-server`");
        }
    }

    Ok(())
}

/// Test provider chain management
#[tokio::test]
async fn test_provider_chain_management() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    // Create config manager directly (bypassing NATS)
    let config_manager = newheads_evm_provider::config::ConfigManager::new(&redis_url)?;
    config_manager.initialize_default_configs().await?;

    // Test chain configuration operations
    let configs = config_manager.load_all_configs().await?;
    println!("✅ Loaded {} chain configurations", configs.len());

    // Test getting a specific chain
    let eth_config = config_manager.load_config("ethereum-mainnet").await?;
    println!(
        "✅ Retrieved Ethereum mainnet config: {}",
        eth_config.chain_name
    );

    // Verify NATS subject structure
    assert_eq!(
        eth_config.nats_subjects.newheads_output,
        "newheads.ethereum.mainnet.evm"
    );
    assert_eq!(eth_config.network, "ethereum");
    assert_eq!(eth_config.subnet, "mainnet");
    assert_eq!(format!("{:?}", eth_config.vm_type).to_lowercase(), "evm");

    // Test Avalanche config
    let avax_config = config_manager.load_config("avalanche-c-chain").await?;
    assert_eq!(
        avax_config.nats_subjects.newheads_output,
        "newheads.avalanche.mainnet.evm"
    );
    assert_eq!(avax_config.network_id, Some(43114));

    println!("✅ Chain management test completed successfully");

    Ok(())
}

/// Test NATS subject patterns for different chains
#[tokio::test]
async fn test_nats_subject_patterns_for_chains() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    let config_manager = newheads_evm_provider::config::ConfigManager::new(&redis_url)?;
    config_manager.initialize_default_configs().await?;

    let configs = config_manager.load_all_configs().await?;

    // Test NATS subject patterns for each chain
    let expected_subjects = vec![
        ("ethereum-mainnet", "newheads.ethereum.mainnet.evm"),
        ("ethereum-goerli", "newheads.ethereum.goerli.evm"),
        ("avalanche-c-chain", "newheads.avalanche.mainnet.evm"),
        ("avalanche-fuji", "newheads.avalanche.fuji.evm"),
    ];

    for (chain_id, expected_subject) in expected_subjects {
        if let Some(config) = configs.get(chain_id) {
            assert_eq!(config.nats_subjects.newheads_output, expected_subject);
            println!("✅ {}: {}", chain_id, expected_subject);

            // Verify subject structure
            let parts: Vec<&str> = expected_subject.split('.').collect();
            assert_eq!(parts.len(), 4, "Subject should have 4 parts");
            assert_eq!(parts[0], "newheads");
            assert_eq!(parts[3], "evm"); // All current chains are EVM
        } else {
            panic!("Missing configuration for chain: {}", chain_id);
        }
    }

    println!("✅ NATS subject pattern test completed successfully");

    Ok(())
}
