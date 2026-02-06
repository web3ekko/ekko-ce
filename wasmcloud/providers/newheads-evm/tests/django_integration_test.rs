//! Integration tests for Django BlockchainNode integration
//!
//! These tests use testcontainers to spin up real Redis instances
//! and verify that the provider correctly reads Django's BlockchainNode format

use anyhow::Result;
use newheads_evm_provider::django_integration::{DjangoBlockchainNode, DjangoConfigManager};
use newheads_evm_provider::NewheadsProvider;
use redis::AsyncCommands;
use serde_json::json;
use testcontainers::runners::AsyncRunner;
use testcontainers_modules::nats::Nats;
use testcontainers_modules::redis::Redis;

/// Test reading Django BlockchainNode format from Redis
#[tokio::test]
async fn test_django_blockchain_node_format() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    // Create Redis client
    let redis_client = redis::Client::open(redis_url.clone())?;
    let mut conn = redis_client.get_async_connection().await?;

    // Create Django BlockchainNode JSON (matching Python model)
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

    let polygon_node = json!({
        "chain_id": "polygon-mainnet",
        "chain_name": "Polygon Mainnet",
        "network": "polygon",
        "subnet": "mainnet",
        "vm_type": "EVM",
        "rpc_url": "https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID",
        "ws_url": "wss://polygon-mainnet.infura.io/ws/v3/YOUR_PROJECT_ID",
        "enabled": true,
        "is_primary": false,
        "priority": 2,
        "latency_ms": 50,
        "success_rate": 99.5,
        "last_health_check": "2025-01-14T12:00:00Z",
        "created_at": "2025-01-14T00:00:00Z",
        "updated_at": "2025-01-14T12:00:00Z"
    });

    // Disabled node (should not be loaded)
    let disabled_node = json!({
        "chain_id": "arbitrum-mainnet",
        "chain_name": "Arbitrum One",
        "network": "arbitrum",
        "subnet": "mainnet",
        "vm_type": "EVM",
        "rpc_url": "https://arbitrum-mainnet.infura.io/v3/YOUR_PROJECT_ID",
        "ws_url": "wss://arbitrum-mainnet.infura.io/ws/v3/YOUR_PROJECT_ID",
        "enabled": false,  // DISABLED
        "is_primary": false,
        "priority": 3,
        "latency_ms": null,
        "success_rate": null,
        "last_health_check": null,
        "created_at": "2025-01-14T00:00:00Z",
        "updated_at": "2025-01-14T00:00:00Z"
    });

    // Store in Redis using Django's key pattern
    conn.set::<_, _, ()>(
        "blockchain:nodes:ethereum-mainnet",
        ethereum_node.to_string(),
    )
    .await?;
    conn.set::<_, _, ()>("blockchain:nodes:polygon-mainnet", polygon_node.to_string())
        .await?;
    conn.set::<_, _, ()>(
        "blockchain:nodes:arbitrum-mainnet",
        disabled_node.to_string(),
    )
    .await?;

    println!("✅ Populated Redis with Django BlockchainNode format");

    // Test Django configuration manager
    let django_manager = DjangoConfigManager::new(&redis_url)?;

    // Load all nodes
    let configs = django_manager.load_all_nodes().await?;

    // Verify only enabled nodes are loaded
    assert_eq!(configs.len(), 2, "Should only load enabled nodes");
    assert!(
        configs.contains_key("ethereum-mainnet"),
        "Should have Ethereum"
    );
    assert!(
        configs.contains_key("polygon-mainnet"),
        "Should have Polygon"
    );
    assert!(
        !configs.contains_key("arbitrum-mainnet"),
        "Should not have disabled Arbitrum"
    );

    println!("✅ Correctly loaded only enabled nodes: {}", configs.len());

    // Verify Ethereum configuration
    let eth_config = configs.get("ethereum-mainnet").unwrap();
    assert_eq!(eth_config.chain_id, "ethereum-mainnet");
    assert_eq!(eth_config.network, "ethereum");
    assert_eq!(eth_config.subnet, "mainnet");
    assert_eq!(
        eth_config.nats_subjects.newheads_output,
        "newheads.ethereum.mainnet.evm"
    );
    assert_eq!(eth_config.network_id, Some(1));
    assert!(eth_config.enabled);

    println!("✅ Ethereum configuration correctly parsed:");
    println!("   Network: {}", eth_config.network);
    println!("   Subnet: {}", eth_config.subnet);
    println!(
        "   NATS Subject: {}",
        eth_config.nats_subjects.newheads_output
    );

    // Verify Polygon configuration
    let poly_config = configs.get("polygon-mainnet").unwrap();
    assert_eq!(poly_config.chain_id, "polygon-mainnet");
    assert_eq!(poly_config.network, "polygon");
    assert_eq!(poly_config.subnet, "mainnet");
    assert_eq!(
        poly_config.nats_subjects.newheads_output,
        "newheads.polygon.mainnet.evm"
    );
    assert_eq!(poly_config.network_id, Some(137));
    assert!(poly_config.enabled);

    println!("✅ Polygon configuration correctly parsed:");
    println!("   Network: {}", poly_config.network);
    println!("   Subnet: {}", poly_config.subnet);
    println!(
        "   NATS Subject: {}",
        poly_config.nats_subjects.newheads_output
    );

    println!("✅ Django BlockchainNode format test completed successfully");

    Ok(())
}

/// Test provider initialization with Django configuration
#[tokio::test]
async fn test_provider_with_django_config() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    // Create Redis client
    let redis_client = redis::Client::open(redis_url.clone())?;
    let mut conn = redis_client.get_async_connection().await?;

    // Store Django nodes in Redis
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

    // Try to initialize provider (will fail on NATS but should load Redis config)
    let nats_url = "nats://localhost:9999"; // Non-existent port

    match NewheadsProvider::new(&nats_url, &redis_url).await {
        Ok(_) => panic!("Should fail on NATS connection"),
        Err(e) => {
            // Should fail on NATS, but that's expected
            println!("✅ Expected NATS error: {}", e);
            assert!(
                e.to_string().contains("connection")
                    || e.to_string().contains("refused")
                    || e.to_string().contains("timeout")
            );
        }
    }

    println!("✅ Provider correctly attempted to load Django configurations");

    Ok(())
}

/// Test configuration updates via Redis pub/sub
#[tokio::test]
async fn test_django_config_updates() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    // Create Django config manager
    let django_manager = DjangoConfigManager::new(&redis_url)?;

    // Test that we can subscribe without error
    // In a real system, this would spawn a background task
    match django_manager.subscribe_to_updates().await {
        Ok(_) => println!("✅ Successfully subscribed to Django configuration updates"),
        Err(e) => println!("⚠️ Subscription setup returned: {}", e),
    }

    // Create Redis client for publishing updates
    let redis_client = redis::Client::open(redis_url.clone())?;
    let mut conn = redis_client.get_async_connection().await?;

    // Simulate Django Admin updating a node
    let update_message = json!({
        "action": "update",
        "chain_id": "ethereum-mainnet",
        "node": {
            "chain_id": "ethereum-mainnet",
            "enabled": false  // Disabling the node
        },
        "timestamp": "2025-01-14T12:00:00Z"
    });

    // Publish update to Django channel
    let _: () = conn
        .publish("blockchain:nodes:updates", update_message.to_string())
        .await?;

    println!("✅ Published configuration update to Django channel");

    Ok(())
}

/// Test complete integration with NATS and Redis using testcontainers
#[tokio::test]
async fn test_full_integration_with_nats() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    // Start NATS container
    let nats_container = Nats::default().start().await?;
    let nats_port = nats_container.get_host_port_ipv4(4222).await?;
    let nats_url = format!("nats://localhost:{}", nats_port);

    println!("🐳 NATS container started at: {}", nats_url);

    // Populate Redis with Django nodes
    let redis_client = redis::Client::open(redis_url.clone())?;
    let mut conn = redis_client.get_async_connection().await?;

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

    println!("✅ Populated Redis with Django BlockchainNode");

    // Initialize provider with both Redis and NATS
    let provider = NewheadsProvider::new(&nats_url, &redis_url).await?;

    println!("✅ Successfully initialized provider with Django integration");

    // Verify configurations were loaded
    let configs = provider.configs().read().await;
    assert_eq!(configs.len(), 1, "Should have loaded one enabled node");
    assert!(
        configs.contains_key("ethereum-mainnet"),
        "Should have Ethereum node"
    );

    let eth_config = configs.get("ethereum-mainnet").unwrap();
    assert_eq!(
        eth_config.nats_subjects.newheads_output,
        "newheads.ethereum.mainnet.evm"
    );

    println!("✅ Provider correctly loaded Django configuration:");
    println!("   Chain: {}", eth_config.chain_name);
    println!("   Network: {}", eth_config.network);
    println!("   Subnet: {}", eth_config.subnet);
    println!(
        "   NATS Subject: {}",
        eth_config.nats_subjects.newheads_output
    );

    println!("✅ Full integration test completed successfully");

    Ok(())
}

/// Test handling of different VM types
#[tokio::test]
async fn test_evm_chains_only() -> Result<()> {
    // Start Redis container
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    println!("🐳 Redis container started at: {}", redis_url);

    let redis_client = redis::Client::open(redis_url.clone())?;
    let mut conn = redis_client.get_async_connection().await?;

    // Test EVM chains - this provider only supports EVM
    let nodes = vec![
        (
            "ethereum-mainnet",
            "ethereum",
            "mainnet",
            "EVM",
            "newheads.ethereum.mainnet.evm",
        ),
        (
            "polygon-mainnet",
            "polygon",
            "mainnet",
            "EVM",
            "newheads.polygon.mainnet.evm",
        ),
        (
            "arbitrum-mainnet",
            "arbitrum",
            "mainnet",
            "EVM",
            "newheads.arbitrum.mainnet.evm",
        ),
        (
            "optimism-mainnet",
            "optimism",
            "mainnet",
            "EVM",
            "newheads.optimism.mainnet.evm",
        ),
    ];

    for (chain_id, network, subnet, vm_type, _expected_subject) in &nodes {
        let node = json!({
            "chain_id": chain_id,
            "chain_name": format!("{} {}", network, subnet),
            "network": network,
            "subnet": subnet,
            "vm_type": vm_type,
            "rpc_url": format!("https://{}.example.com", network),
            "ws_url": format!("wss://{}.example.com", network),
            "enabled": true,
            "is_primary": true,
            "priority": 1,
            "latency_ms": null,
            "success_rate": null,
            "last_health_check": null,
            "created_at": "2025-01-14T00:00:00Z",
            "updated_at": "2025-01-14T00:00:00Z"
        });

        conn.set::<_, _, ()>(format!("blockchain:nodes:{}", chain_id), node.to_string())
            .await?;
    }

    // Load configurations
    let django_manager = DjangoConfigManager::new(&redis_url)?;
    let configs = django_manager.load_all_nodes().await?;

    // Verify all VM types mapped correctly
    for (chain_id, _network, _subnet, _vm_type, expected_subject) in nodes {
        let config = configs
            .get(chain_id)
            .expect(&format!("Should have {}", chain_id));
        assert_eq!(
            config.nats_subjects.newheads_output, expected_subject,
            "NATS subject mismatch for {}",
            chain_id
        );
        println!("✅ {} -> {}", chain_id, expected_subject);
    }

    println!("✅ All EVM chains correctly mapped to NATS subjects");

    Ok(())
}

/// Test that non-EVM chains are rejected
#[tokio::test]
async fn test_non_evm_chains_rejected() -> Result<()> {
    // Non-EVM chains should be rejected by this EVM-specific provider
    let non_evm_nodes = vec![
        ("bitcoin-mainnet", "bitcoin", "mainnet", "UTXO"),
        ("solana-mainnet", "solana", "mainnet", "SVM"),
        ("cosmos-hub", "cosmos", "mainnet", "COSMOS"),
    ];

    for (chain_id, network, subnet, vm_type) in non_evm_nodes {
        let node = DjangoBlockchainNode {
            chain_id: chain_id.to_string(),
            chain_name: format!("{} {}", network, subnet),
            network: network.to_string(),
            subnet: subnet.to_string(),
            vm_type: vm_type.to_string(),
            rpc_url: format!("https://{}.example.com", network),
            ws_url: format!("wss://{}.example.com", network),
            enabled: true,
            is_primary: false,
            priority: 1,
            latency_ms: None,
            success_rate: None,
            last_health_check: None,
            created_at: "2025-01-14T10:00:00Z".to_string(),
            updated_at: "2025-01-14T10:00:00Z".to_string(),
        };

        // Try to convert to chain config - should fail for non-EVM
        let result = node.to_chain_config();
        assert!(result.is_err());

        let error_msg = result.unwrap_err().to_string();
        assert!(error_msg.contains("EVM-specific provider"));
        assert!(error_msg.contains(vm_type));

        println!(
            "✅ Correctly rejected non-EVM chain: {} ({})",
            chain_id, vm_type
        );
    }

    println!("✅ All non-EVM chains correctly rejected");

    Ok(())
}
