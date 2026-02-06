//! Comprehensive integration tests for newheads EVM provider
//!
//! These tests use testcontainers to create a complete test environment
//! with Redis, NATS, and mock blockchain endpoints to validate all
//! provider functionality including subscription management, client creation,
//! and error handling.

use anyhow::Result;
use newheads_evm_provider::{
    config::ConfigManager, django_integration::DjangoConfigManager, traits::*, NewheadsProvider,
};
use redis::AsyncCommands;
use serde_json::json;
use std::time::Duration;
use testcontainers::{runners::AsyncRunner, ContainerAsync};
use testcontainers_modules::{nats::Nats, redis::Redis};
use tokio::time::sleep;

/// Comprehensive test environment with Redis and NATS containers
struct ProviderTestEnvironment {
    _redis: ContainerAsync<Redis>,
    _nats: ContainerAsync<Nats>,
    redis_url: String,
    nats_url: String,
    provider: Option<NewheadsProvider>,
    config_manager: ConfigManager,
    django_config_manager: DjangoConfigManager,
}

impl ProviderTestEnvironment {
    /// Set up test environment with Redis and NATS containers
    async fn new() -> Result<Self> {
        // Start Redis container
        let redis = Redis::default().start().await?;
        let redis_port = redis.get_host_port_ipv4(6379).await?;
        let redis_url = format!("redis://127.0.0.1:{}", redis_port);

        // Start NATS container
        let nats = Nats::default().start().await?;
        let nats_port = nats.get_host_port_ipv4(4222).await?;
        let nats_url = format!("nats://127.0.0.1:{}", nats_port);

        // Wait for containers to be ready
        sleep(Duration::from_secs(8)).await;

        // Create config managers
        let config_manager = ConfigManager::new(&redis_url)?;
        let django_config_manager = DjangoConfigManager::new(&redis_url)?;

        println!("🐳 Provider test environment ready:");
        println!("  Redis: {}", redis_url);
        println!("  NATS: {}", nats_url);

        Ok(Self {
            _redis: redis,
            _nats: nats,
            redis_url: redis_url.clone(),
            nats_url,
            provider: None,
            config_manager,
            django_config_manager,
        })
    }

    /// Initialize provider with the test environment
    async fn init_provider(&mut self) -> Result<()> {
        self.provider = Some(NewheadsProvider::new(&self.nats_url, &self.redis_url).await?);
        Ok(())
    }

    /// Get provider reference (panics if not initialized)
    fn provider(&self) -> &NewheadsProvider {
        self.provider.as_ref().expect("Provider not initialized")
    }

    /// Set up test configurations in Redis using Django format
    async fn setup_test_configs(&self) -> Result<()> {
        // Initialize default configs through ConfigManager
        self.config_manager.initialize_default_configs().await?;

        // Add a test configuration using Django format
        let redis_client = redis::Client::open(self.redis_url.clone())?;
        let mut conn = redis_client.get_async_connection().await?;

        let test_node = json!({
            "chain_id": "test-ethereum",
            "chain_name": "Test Ethereum",
            "network": "ethereum",
            "subnet": "test",
            "vm_type": "EVM",
            "rpc_url": "http://mock-ethereum:8545",
            "ws_url": "ws://mock-ethereum:8546",
            "enabled": true,
            "is_primary": true,
            "priority": 1,
            "latency_ms": null,
            "success_rate": null,
            "last_health_check": null,
            "created_at": "2025-01-14T00:00:00Z",
            "updated_at": "2025-01-14T00:00:00Z"
        });

        // Store in Django's key pattern
        conn.set::<_, _, ()>("blockchain:nodes:test-ethereum", test_node.to_string())
            .await?;

        // Also add standard EVM configs in Django format
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

        Ok(())
    }
}

#[tokio::test]
async fn test_provider_environment_setup() -> Result<()> {
    let _env = ProviderTestEnvironment::new().await?;

    println!("✅ Provider test environment setup successful");
    Ok(())
}

#[tokio::test]
async fn test_provider_initialization_with_containers() -> Result<()> {
    let mut env = ProviderTestEnvironment::new().await?;

    // Setup test configurations
    env.setup_test_configs().await?;

    // Initialize provider
    env.init_provider().await?;

    // Verify provider is initialized
    let provider = env.provider();
    let configs = provider.configs().read().await;
    assert!(
        !configs.is_empty(),
        "Provider should have loaded configurations"
    );

    println!(
        "✅ Provider initialized successfully with {} configurations",
        configs.len()
    );
    Ok(())
}

#[tokio::test]
async fn test_configuration_loading_and_validation() -> Result<()> {
    let mut env = ProviderTestEnvironment::new().await?;

    // Setup test configurations
    env.setup_test_configs().await?;
    env.init_provider().await?;

    let provider = env.provider();
    let configs = provider.configs().read().await;

    // Verify test configuration was loaded
    assert!(
        configs.contains_key("test-ethereum"),
        "Test configuration should be loaded"
    );

    let test_config = configs.get("test-ethereum").unwrap();
    assert_eq!(test_config.chain_name, "Test Ethereum");
    assert_eq!(test_config.network, "ethereum");
    assert_eq!(test_config.subnet, "test");
    assert_eq!(
        test_config.nats_subjects.newheads_output,
        "newheads.ethereum.test.evm"
    );

    // Verify at least one configuration was loaded
    assert!(
        configs.contains_key("ethereum-mainnet"),
        "Should have ethereum-mainnet config"
    );

    println!("✅ Configuration loading and validation successful");
    Ok(())
}

#[tokio::test]
async fn test_subscription_attempt() -> Result<()> {
    let mut env = ProviderTestEnvironment::new().await?;

    env.setup_test_configs().await?;
    env.init_provider().await?;

    let provider = env.provider();

    // Test subscription attempt (will fail with mock URL, which is expected)
    let result = provider.subscribe_newheads("test-ethereum").await;
    assert!(
        result.is_err(),
        "Expected subscription to fail with mock URL"
    );

    let error_msg = result.unwrap_err().to_string();
    assert!(
        error_msg.contains("connection")
            || error_msg.contains("refused")
            || error_msg.contains("timeout")
            || error_msg.contains("resolve")
            || error_msg.contains("dns error")
            || error_msg.contains("lookup")
            || error_msg.contains("Chain 'test-ethereum' not found"),
        "Expected connection error or chain not found, got: {}",
        error_msg
    );

    println!("✅ Subscription attempt handling works correctly");
    Ok(())
}

#[tokio::test]
async fn test_subscription_error_handling() -> Result<()> {
    let mut env = ProviderTestEnvironment::new().await?;

    env.setup_test_configs().await?;
    env.init_provider().await?;

    let provider = env.provider();

    // Test subscription to non-existent chain
    let result = provider.subscribe_newheads("non-existent-chain").await;
    assert!(result.is_err(), "Should fail for non-existent chain");

    let error_msg = result.unwrap_err().to_string();
    assert!(
        error_msg.contains("not found") || error_msg.contains("No configuration"),
        "Error should indicate missing configuration: {}",
        error_msg
    );

    // Test subscription with invalid RPC URL (should fail gracefully)
    let result = provider.subscribe_newheads("test-ethereum").await;
    assert!(result.is_err(), "Should fail with mock RPC URL");

    println!("✅ Subscription error handling works correctly");
    Ok(())
}

#[tokio::test]
async fn test_nats_subject_validation() -> Result<()> {
    let env = ProviderTestEnvironment::new().await?;

    env.setup_test_configs().await?;

    // Load configs through Django config manager for this test
    let configs = env.django_config_manager.load_all_nodes().await?;

    // Test NATS subject patterns
    for (chain_id, config) in configs {
        let subject = &config.nats_subjects.newheads_output;
        let parts: Vec<&str> = subject.split('.').collect();

        // Validate subject structure: newheads.{network}.{subnet}.{vm_type}
        assert_eq!(parts.len(), 4, "Subject '{}' should have 4 parts", subject);
        assert_eq!(parts[0], "newheads", "First part should be 'newheads'");
        assert_eq!(parts[1], config.network, "Second part should match network");
        assert_eq!(parts[2], config.subnet, "Third part should match subnet");

        // Validate VM type mapping - this is an EVM-specific provider
        assert_eq!(
            parts[3], "evm",
            "Fourth part should be 'evm' for this EVM-specific provider"
        );

        println!("✅ {}: {}", chain_id, subject);
    }

    println!("✅ NATS subject validation successful");
    Ok(())
}

#[tokio::test]
async fn test_concurrent_operations() -> Result<()> {
    let mut env = ProviderTestEnvironment::new().await?;

    env.setup_test_configs().await?;
    env.init_provider().await?;

    let provider = env.provider();

    // Test concurrent configuration access
    let handles: Vec<_> = (0..10)
        .map(|i| {
            let provider_clone = provider.clone();
            tokio::spawn(async move {
                let configs = provider_clone.configs().read().await;
                assert!(
                    !configs.is_empty(),
                    "Configs should be available in task {}",
                    i
                );
                configs.len()
            })
        })
        .collect();

    // Wait for all tasks to complete
    let results: Vec<_> = futures::future::join_all(handles).await;

    // All tasks should succeed and return the same config count
    let config_counts: Vec<_> = results.into_iter().map(|r| r.unwrap()).collect();
    let first_count = config_counts[0];
    assert!(
        config_counts.iter().all(|&count| count == first_count),
        "All tasks should see the same number of configurations"
    );

    println!("✅ Concurrent operations work correctly");
    Ok(())
}

#[tokio::test]
async fn test_performance_metrics() -> Result<()> {
    let mut env = ProviderTestEnvironment::new().await?;

    env.setup_test_configs().await?;

    let start_time = std::time::Instant::now();

    // Measure configuration loading time through Django config manager
    let configs = env.django_config_manager.load_all_nodes().await?;
    let load_time = start_time.elapsed();

    // Initialize provider
    env.init_provider().await?;
    let init_time = start_time.elapsed();

    println!("✅ Performance metrics:");
    println!("  Config loading: {:?}", load_time);
    println!("  Provider init: {:?}", init_time);
    println!("  Configurations loaded: {}", configs.len());
    println!(
        "  Avg time per config: {:?}",
        load_time / configs.len() as u32
    );

    // Performance assertions
    assert!(
        load_time < Duration::from_secs(5),
        "Config loading should be fast"
    );
    assert!(
        init_time < Duration::from_secs(10),
        "Provider init should be reasonable"
    );
    assert!(configs.len() >= 2, "Should load multiple configurations");

    Ok(())
}

#[tokio::test]
async fn test_basic_configuration_validation() -> Result<()> {
    let env = ProviderTestEnvironment::new().await?;

    env.setup_test_configs().await?;

    // Load configs through Django config manager
    let configs = env.django_config_manager.load_all_nodes().await?;

    // Verify basic configuration fields
    for (chain_id, config) in configs {
        assert!(
            !config.chain_name.is_empty(),
            "Chain name should not be empty for {}",
            chain_id
        );
        assert!(
            !config.network.is_empty(),
            "Network should not be empty for {}",
            chain_id
        );
        assert!(
            !config.subnet.is_empty(),
            "Subnet should not be empty for {}",
            chain_id
        );
        assert!(
            !config.rpc_url.is_empty(),
            "RPC URL should not be empty for {}",
            chain_id
        );
        assert!(
            !config.ws_url.is_empty(),
            "WS URL should not be empty for {}",
            chain_id
        );

        println!("✅ {}: Basic config valid", chain_id);
    }

    Ok(())
}

#[tokio::test]
async fn test_evm_specific_validation() -> Result<()> {
    let env = ProviderTestEnvironment::new().await?;

    env.setup_test_configs().await?;

    // Test that non-EVM chains are rejected
    let redis_client = redis::Client::open(env.redis_url.clone())?;
    let mut conn = redis_client.get_async_connection().await?;

    // Try to add a Bitcoin (UTXO) node
    let bitcoin_node = json!({
        "chain_id": "bitcoin-mainnet",
        "chain_name": "Bitcoin Mainnet",
        "network": "bitcoin",
        "subnet": "mainnet",
        "vm_type": "UTXO",  // Non-EVM type
        "rpc_url": "https://bitcoin.example.com",
        "ws_url": "wss://bitcoin.example.com",
        "enabled": true,
        "is_primary": true,
        "priority": 1,
        "latency_ms": null,
        "success_rate": null,
        "last_health_check": null,
        "created_at": "2025-01-14T00:00:00Z",
        "updated_at": "2025-01-14T00:00:00Z"
    });

    conn.set::<_, _, ()>("blockchain:nodes:bitcoin-mainnet", bitcoin_node.to_string())
        .await?;

    // Try to load through Django config manager - should reject non-EVM
    let configs = env.django_config_manager.load_all_nodes().await?;

    // Bitcoin should not be in the loaded configs
    assert!(
        !configs.contains_key("bitcoin-mainnet"),
        "Non-EVM chain (Bitcoin) should not be loaded by EVM-specific provider"
    );

    // Only EVM chains should be loaded
    for (_chain_id, config) in &configs {
        assert_eq!(
            config.vm_type,
            VmType::Evm,
            "Only EVM chains should be loaded"
        );
    }

    println!("✅ EVM-specific validation successful - non-EVM chains rejected");
    Ok(())
}
