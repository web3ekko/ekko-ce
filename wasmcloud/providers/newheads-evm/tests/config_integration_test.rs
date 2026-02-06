//! Integration tests for newheads provider configuration
//!
//! These tests use testcontainers to spin up real Redis instances

use anyhow::Result;
use newheads_evm_provider::config::{ConfigAction, ConfigChangeMessage, ConfigManager};
use testcontainers::runners::AsyncRunner;
use testcontainers_modules::redis::Redis;

/// Test Redis configuration management with testcontainers
#[tokio::test]
async fn test_redis_config_with_testcontainers() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    // Test Redis configuration management
    let config_manager = ConfigManager::new(&redis_url)?;

    // Initialize default configs
    config_manager.initialize_default_configs().await?;
    println!("✅ Initialized default chain configurations");

    // Load all configs
    let configs = config_manager.load_all_configs().await?;
    println!(
        "✅ Loaded {} chain configurations from Redis",
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

    // Test loading a specific config
    let eth_config = config_manager.load_config("ethereum-mainnet").await?;
    println!("✅ Successfully loaded Ethereum mainnet config:");
    println!("   Chain Name: {}", eth_config.chain_name);
    println!("   Network: {}", eth_config.network);
    println!("   Subnet: {}", eth_config.subnet);
    println!("   VM Type: {:?}", eth_config.vm_type);
    println!(
        "   NATS Subject: {}",
        eth_config.nats_subjects.newheads_output
    );

    // Test NATS subject structure
    assert_eq!(
        eth_config.nats_subjects.newheads_output,
        "newheads.ethereum.mainnet.evm"
    );
    assert_eq!(
        eth_config.nats_subjects.config_input,
        "config.ethereum-mainnet.input"
    );
    assert_eq!(
        eth_config.nats_subjects.status_output,
        "status.ethereum-mainnet.output"
    );
    assert_eq!(
        eth_config.nats_subjects.control_input,
        "control.ethereum-mainnet.input"
    );

    // Test Avalanche config
    let avax_config = config_manager.load_config("avalanche-c-chain").await?;
    assert_eq!(
        avax_config.nats_subjects.newheads_output,
        "newheads.avalanche.mainnet.evm"
    );
    assert_eq!(avax_config.network_id, Some(43114));

    println!("✅ Redis configuration test completed successfully");

    // Container will be automatically stopped when it goes out of scope
    Ok(())
}

/// Test configuration message serialization
#[tokio::test]
async fn test_config_message_serialization() -> Result<()> {
    println!("🧪 Testing configuration message serialization");

    // Test config change message serialization
    let config_change = ConfigChangeMessage {
        action: ConfigAction::Reload,
        chain_id: "test".to_string(),
        config: None,
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_secs(),
    };

    let message = serde_json::to_vec(&config_change)?;
    assert!(!message.is_empty());
    println!(
        "✅ Config change message serialization works: {} bytes",
        message.len()
    );

    // Test deserialization
    let deserialized: ConfigChangeMessage = serde_json::from_slice(&message)?;
    assert_eq!(deserialized.chain_id, "test");
    assert!(matches!(deserialized.action, ConfigAction::Reload));

    // Test different config actions
    let actions = vec![
        ConfigAction::Add,
        ConfigAction::Update,
        ConfigAction::Remove,
        ConfigAction::Enable,
        ConfigAction::Disable,
        ConfigAction::Reload,
    ];

    for action in actions {
        let msg = ConfigChangeMessage {
            action: action.clone(),
            chain_id: "test-chain".to_string(),
            config: None,
            timestamp: 1699000000,
        };

        let serialized = serde_json::to_vec(&msg)?;
        let deserialized: ConfigChangeMessage = serde_json::from_slice(&serialized)?;

        // Use Debug trait for comparison since ConfigAction doesn't implement PartialEq
        assert_eq!(
            format!("{:?}", deserialized.action),
            format!("{:?}", action)
        );
        println!("   ✓ Action serialization works: {:?}", action);
    }

    println!("✅ Configuration message serialization test completed");

    Ok(())
}

/// Test NATS subject patterns and validation
#[tokio::test]
async fn test_nats_subject_patterns() -> Result<()> {
    println!("🧪 Testing NATS subject patterns");

    // Test valid subject patterns
    let test_subjects = vec![
        ("newheads.ethereum.mainnet.evm", true),
        ("newheads.avalanche.mainnet.evm", true),
        ("newheads.bitcoin.mainnet.utxo", true),
        ("newheads.solana.mainnet.svm", true),
        ("config.ethereum-mainnet.input", true),
        ("status.ethereum-mainnet.output", true),
        ("control.ethereum-mainnet.input", true),
        // Invalid patterns
        ("newheads.ethereum", false),
        ("newheads.ethereum.mainnet", false),
        ("invalid.subject.pattern.too.many.parts", false),
    ];

    for (subject, should_be_valid) in test_subjects {
        let parts: Vec<&str> = subject.split('.').collect();

        if subject.starts_with("newheads.") {
            let is_valid = parts.len() == 4 && parts[0] == "newheads";
            assert_eq!(
                is_valid, should_be_valid,
                "Subject validation failed for: {}",
                subject
            );

            if is_valid {
                println!("   ✓ Valid newheads subject: {}", subject);
                // Additional validation for newheads subjects
                assert!(!parts[1].is_empty(), "Network part should not be empty");
                assert!(!parts[2].is_empty(), "Subnet part should not be empty");
                assert!(!parts[3].is_empty(), "EVM type part should not be empty");
            }
        } else if subject.starts_with("config.")
            || subject.starts_with("status.")
            || subject.starts_with("control.")
        {
            let is_valid = parts.len() == 3;
            assert_eq!(
                is_valid, should_be_valid,
                "Subject validation failed for: {}",
                subject
            );

            if is_valid {
                println!("   ✓ Valid control subject: {}", subject);
            }
        }
    }

    println!("✅ NATS subject pattern test completed");

    Ok(())
}

/// Test mock blockchain data structures
#[tokio::test]
async fn test_mock_blockchain_data() -> Result<()> {
    println!("🧪 Testing mock blockchain data structures");

    // Test mock newheads message serialization
    let mock_newheads = serde_json::json!({
        "chain_id": "ethereum-mainnet",
        "chain_name": "Ethereum Mainnet",
        "block_number": 18500000,
        "block_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "parent_hash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "timestamp": 1699000000,
        "difficulty": "0x1bc16d674ec80000",
        "gas_limit": 30000000,
        "gas_used": 15000000,
        "miner": "0x1234567890123456789012345678901234567890"
    });

    let newheads_message = serde_json::to_vec(&mock_newheads)?;
    assert!(!newheads_message.is_empty());
    println!(
        "✅ Newheads message serialization works: {} bytes",
        newheads_message.len()
    );

    // Verify the structure
    assert_eq!(mock_newheads["chain_id"], "ethereum-mainnet");
    assert_eq!(mock_newheads["block_number"], 18500000);
    assert!(mock_newheads["block_hash"]
        .as_str()
        .unwrap()
        .starts_with("0x"));
    assert!(mock_newheads["block_hash"].as_str().unwrap().len() == 66); // 0x + 64 hex chars

    println!("✅ Mock blockchain data test completed");

    Ok(())
}

/// Test configuration persistence across Redis restarts
#[tokio::test]
async fn test_config_persistence() -> Result<()> {
    println!("🧪 Testing configuration persistence");

    // Start first Redis container
    let redis_container1 = Redis::default().start().await?;
    let redis_port1 = redis_container1.get_host_port_ipv4(6379).await?;
    let redis_url1 = format!("redis://localhost:{}", redis_port1);

    // Initialize configs in first container
    let config_manager1 = ConfigManager::new(&redis_url1)?;
    config_manager1.initialize_default_configs().await?;

    let configs_before = config_manager1.load_all_configs().await?;
    let config_count = configs_before.len();
    println!(
        "✅ Stored {} configurations in first Redis instance",
        config_count
    );

    // Drop the first container (simulating restart)
    drop(redis_container1);

    // Start second Redis container (fresh instance)
    let redis_container2 = Redis::default().start().await?;
    let redis_port2 = redis_container2.get_host_port_ipv4(6379).await?;
    let redis_url2 = format!("redis://localhost:{}", redis_port2);

    // Try to load configs from fresh instance (should be empty)
    let config_manager2 = ConfigManager::new(&redis_url2)?;
    let configs_after = config_manager2.load_all_configs().await?;

    // Fresh Redis should be empty
    assert_eq!(
        configs_after.len(),
        0,
        "Fresh Redis instance should be empty"
    );
    println!("✅ Fresh Redis instance is empty as expected");

    // Re-initialize configs
    config_manager2.initialize_default_configs().await?;
    let configs_reinitialized = config_manager2.load_all_configs().await?;

    // Should have same number of configs as before
    assert_eq!(
        configs_reinitialized.len(),
        config_count,
        "Reinitialized configs should match original count"
    );
    println!("✅ Configuration reinitialization works correctly");

    Ok(())
}
