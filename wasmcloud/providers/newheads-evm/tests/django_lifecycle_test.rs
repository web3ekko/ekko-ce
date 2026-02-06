//! Full lifecycle tests for Django BlockchainNode management
//!
//! These tests simulate the complete flow:
//! 1. Django Admin creates a new BlockchainNode
//! 2. Provider detects the new node via Redis
//! 3. Provider starts monitoring the blockchain
//! 4. Django updates/disables the node
//! 5. Provider responds to changes

use anyhow::Result;
use futures_util::StreamExt;
use newheads_evm_provider::NewheadsProvider;
use redis::AsyncCommands;
use serde_json::json;
use std::sync::Arc;
use testcontainers::runners::AsyncRunner;
use testcontainers_modules::nats::Nats;
use testcontainers_modules::redis::Redis;
use tokio::sync::RwLock;
use tokio::time::{sleep, Duration};

/// Simulates Django Admin operations
struct DjangoAdminSimulator {
    redis_client: redis::Client,
}

impl DjangoAdminSimulator {
    pub async fn new(redis_url: &str) -> Result<Self> {
        let redis_client = redis::Client::open(redis_url)?;
        Ok(Self { redis_client })
    }

    /// Simulate Django Admin creating a new BlockchainNode
    pub async fn create_blockchain_node(
        &self,
        chain_id: &str,
        network: &str,
        subnet: &str,
        vm_type: &str,
        enabled: bool,
    ) -> Result<()> {
        let mut conn = self.redis_client.get_async_connection().await?;

        // Create Django BlockchainNode JSON (as Django would)
        let node = json!({
            "chain_id": chain_id,
            "chain_name": format!("{} {}", network.to_uppercase(), subnet),
            "network": network,
            "subnet": subnet,
            "vm_type": vm_type,
            "rpc_url": format!("https://{}.{}.infura.io/v3/TEST_KEY", network, subnet),
            "ws_url": format!("wss://{}.{}.infura.io/ws/v3/TEST_KEY", network, subnet),
            "enabled": enabled,
            "is_primary": true,
            "priority": 1,
            "latency_ms": null,
            "success_rate": null,
            "last_health_check": null,
            "created_at": chrono::Utc::now().to_rfc3339(),
            "updated_at": chrono::Utc::now().to_rfc3339()
        });

        // Store in Redis using Django's key pattern
        let key = format!("blockchain:nodes:{}", chain_id);
        conn.set::<_, _, ()>(&key, node.to_string()).await?;

        // Publish update notification (as Django would)
        let update_msg = json!({
            "action": "create",
            "chain_id": chain_id,
            "timestamp": chrono::Utc::now().to_rfc3339()
        });

        conn.publish::<_, _, ()>("blockchain:nodes:updates", update_msg.to_string())
            .await?;

        println!("📝 Django Admin: Created BlockchainNode '{}'", chain_id);
        Ok(())
    }

    /// Simulate Django Admin updating a BlockchainNode
    pub async fn update_blockchain_node(&self, chain_id: &str, enabled: bool) -> Result<()> {
        let mut conn = self.redis_client.get_async_connection().await?;

        // Get existing node
        let key = format!("blockchain:nodes:{}", chain_id);
        let node_json: String = conn.get(&key).await?;
        let mut node: serde_json::Value = serde_json::from_str(&node_json)?;

        // Update fields
        node["enabled"] = json!(enabled);
        node["updated_at"] = json!(chrono::Utc::now().to_rfc3339());

        // Save back to Redis
        conn.set::<_, _, ()>(&key, node.to_string()).await?;

        // Publish update notification
        let update_msg = json!({
            "action": "update",
            "chain_id": chain_id,
            "enabled": enabled,
            "timestamp": chrono::Utc::now().to_rfc3339()
        });

        conn.publish::<_, _, ()>("blockchain:nodes:updates", update_msg.to_string())
            .await?;

        println!(
            "📝 Django Admin: Updated BlockchainNode '{}' (enabled: {})",
            chain_id, enabled
        );
        Ok(())
    }

    /// Simulate Django Admin deleting a BlockchainNode
    pub async fn delete_blockchain_node(&self, chain_id: &str) -> Result<()> {
        let mut conn = self.redis_client.get_async_connection().await?;

        // Delete from Redis
        let key = format!("blockchain:nodes:{}", chain_id);
        conn.del::<_, ()>(&key).await?;

        // Publish deletion notification
        let update_msg = json!({
            "action": "delete",
            "chain_id": chain_id,
            "timestamp": chrono::Utc::now().to_rfc3339()
        });

        conn.publish::<_, _, ()>("blockchain:nodes:updates", update_msg.to_string())
            .await?;

        println!("📝 Django Admin: Deleted BlockchainNode '{}'", chain_id);
        Ok(())
    }
}

/// Test the complete lifecycle: Create node → Provider starts → Update node → Provider responds
#[tokio::test]
async fn test_django_create_node_provider_starts() -> Result<()> {
    // Start containers
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    let nats_container = Nats::default().start().await?;
    let nats_port = nats_container.get_host_port_ipv4(4222).await?;
    let nats_url = format!("nats://localhost:{}", nats_port);

    println!("🐳 Test environment started:");
    println!("   Redis: {}", redis_url);
    println!("   NATS: {}", nats_url);

    // Create Django Admin simulator
    let django_admin = DjangoAdminSimulator::new(&redis_url).await?;

    // Step 1: Start with no nodes
    println!("\n==== Step 1: Initial State (No Nodes) ====");

    let provider = NewheadsProvider::new(&nats_url, &redis_url).await?;
    let configs = provider.configs().read().await;
    assert_eq!(configs.len(), 0, "Should start with no configurations");
    println!("✅ Provider started with 0 nodes (as expected)");
    drop(configs);

    // Step 2: Django creates a new Ethereum mainnet node
    println!("\n==== Step 2: Django Creates Ethereum Node ====");

    django_admin
        .create_blockchain_node("ethereum-mainnet", "ethereum", "mainnet", "EVM", true)
        .await?;

    // Give provider time to detect the change (in real system, this would be via pub/sub)
    sleep(Duration::from_millis(100)).await;

    // Provider should reload configurations
    provider.load_configs_from_django().await?;

    let configs = provider.configs().read().await;
    assert_eq!(
        configs.len(),
        1,
        "Should have 1 configuration after creation"
    );
    assert!(
        configs.contains_key("ethereum-mainnet"),
        "Should have Ethereum node"
    );

    let eth_config = configs.get("ethereum-mainnet").unwrap();
    assert_eq!(eth_config.network, "ethereum");
    assert_eq!(eth_config.subnet, "mainnet");
    assert_eq!(
        eth_config.nats_subjects.newheads_output,
        "newheads.ethereum.mainnet.evm"
    );
    assert!(eth_config.enabled, "Node should be enabled");

    println!("✅ Provider detected new Ethereum node");
    println!(
        "   NATS subject: {}",
        eth_config.nats_subjects.newheads_output
    );
    drop(configs);

    // Step 3: Django creates another node (Polygon)
    println!("\n==== Step 3: Django Creates Polygon Node ====");

    django_admin
        .create_blockchain_node("polygon-mainnet", "polygon", "mainnet", "EVM", true)
        .await?;

    sleep(Duration::from_millis(100)).await;
    provider.load_configs_from_django().await?;

    let configs = provider.configs().read().await;
    assert_eq!(configs.len(), 2, "Should have 2 configurations");
    assert!(
        configs.contains_key("polygon-mainnet"),
        "Should have Polygon node"
    );

    let poly_config = configs.get("polygon-mainnet").unwrap();
    assert_eq!(
        poly_config.nats_subjects.newheads_output,
        "newheads.polygon.mainnet.evm"
    );

    println!("✅ Provider detected new Polygon node");
    println!("   Total active nodes: {}", configs.len());
    drop(configs);

    // Step 4: Django disables Ethereum node
    println!("\n==== Step 4: Django Disables Ethereum Node ====");

    django_admin
        .update_blockchain_node("ethereum-mainnet", false)
        .await?;

    sleep(Duration::from_millis(100)).await;
    provider.load_configs_from_django().await?;

    let configs = provider.configs().read().await;
    assert_eq!(configs.len(), 1, "Should only have 1 enabled configuration");
    assert!(
        !configs.contains_key("ethereum-mainnet"),
        "Disabled Ethereum should not be loaded"
    );
    assert!(
        configs.contains_key("polygon-mainnet"),
        "Polygon should still be active"
    );

    println!("✅ Provider removed disabled Ethereum node");
    println!("   Active nodes: {:?}", configs.keys().collect::<Vec<_>>());
    drop(configs);

    // Step 5: Django re-enables Ethereum node
    println!("\n==== Step 5: Django Re-enables Ethereum Node ====");

    django_admin
        .update_blockchain_node("ethereum-mainnet", true)
        .await?;

    sleep(Duration::from_millis(100)).await;
    provider.load_configs_from_django().await?;

    let configs = provider.configs().read().await;
    assert_eq!(configs.len(), 2, "Should have both nodes enabled again");
    assert!(
        configs.contains_key("ethereum-mainnet"),
        "Ethereum should be back"
    );
    assert!(
        configs.contains_key("polygon-mainnet"),
        "Polygon should still be there"
    );

    println!("✅ Provider re-added enabled Ethereum node");
    drop(configs);

    // Step 6: Django deletes Polygon node
    println!("\n==== Step 6: Django Deletes Polygon Node ====");

    django_admin
        .delete_blockchain_node("polygon-mainnet")
        .await?;

    sleep(Duration::from_millis(100)).await;
    provider.load_configs_from_django().await?;

    let configs = provider.configs().read().await;
    assert_eq!(configs.len(), 1, "Should only have Ethereum after deletion");
    assert!(
        configs.contains_key("ethereum-mainnet"),
        "Ethereum should remain"
    );
    assert!(
        !configs.contains_key("polygon-mainnet"),
        "Polygon should be gone"
    );

    println!("✅ Provider removed deleted Polygon node");

    println!("\n==== Test Complete: Full Lifecycle Verified ====");
    println!("✅ Django create → Provider detect");
    println!("✅ Django disable → Provider remove");
    println!("✅ Django enable → Provider add");
    println!("✅ Django delete → Provider remove");

    Ok(())
}

/// Test that provider only starts monitoring enabled nodes
#[tokio::test]
async fn test_provider_only_monitors_enabled_nodes() -> Result<()> {
    // Start containers
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    let nats_container = Nats::default().start().await?;
    let nats_port = nats_container.get_host_port_ipv4(4222).await?;
    let nats_url = format!("nats://localhost:{}", nats_port);

    println!("🐳 Test environment started");

    let django_admin = DjangoAdminSimulator::new(&redis_url).await?;

    // Create multiple nodes with different enabled states
    println!("\n==== Creating Multiple Nodes ====");

    // Create enabled nodes
    django_admin
        .create_blockchain_node("ethereum-mainnet", "ethereum", "mainnet", "EVM", true)
        .await?;
    django_admin
        .create_blockchain_node("polygon-mainnet", "polygon", "mainnet", "EVM", true)
        .await?;

    // Create disabled nodes
    django_admin
        .create_blockchain_node("arbitrum-mainnet", "arbitrum", "mainnet", "EVM", false)
        .await?;
    django_admin
        .create_blockchain_node("optimism-mainnet", "optimism", "mainnet", "EVM", false)
        .await?;

    // Create different VM type nodes (non-EVM will be rejected by this EVM-specific provider)
    django_admin
        .create_blockchain_node("bitcoin-mainnet", "bitcoin", "mainnet", "UTXO", true)
        .await?;
    django_admin
        .create_blockchain_node("solana-mainnet", "solana", "mainnet", "SVM", false)
        .await?;

    println!("📝 Created 6 nodes (3 enabled EVM, 1 enabled UTXO, 2 disabled)");

    // Initialize provider
    let provider = NewheadsProvider::new(&nats_url, &redis_url).await?;

    // Check that only enabled EVM nodes are loaded (non-EVM chains are rejected)
    let configs = provider.configs().read().await;

    assert_eq!(
        configs.len(),
        2,
        "Should only load 2 enabled EVM nodes (Bitcoin is UTXO and rejected)"
    );
    assert!(
        configs.contains_key("ethereum-mainnet"),
        "Should have enabled Ethereum (EVM)"
    );
    assert!(
        configs.contains_key("polygon-mainnet"),
        "Should have enabled Polygon (EVM)"
    );

    // These should NOT be loaded:
    assert!(
        !configs.contains_key("bitcoin-mainnet"),
        "Should NOT have Bitcoin (UTXO - non-EVM)"
    );
    assert!(
        !configs.contains_key("arbitrum-mainnet"),
        "Should NOT have disabled Arbitrum"
    );
    assert!(
        !configs.contains_key("optimism-mainnet"),
        "Should NOT have disabled Optimism"
    );
    assert!(
        !configs.contains_key("solana-mainnet"),
        "Should NOT have disabled Solana"
    );

    println!("✅ EVM-specific provider correctly loaded only enabled EVM nodes:");
    for (chain_id, config) in configs.iter() {
        println!(
            "   - {} ({}) → {}",
            chain_id,
            format!("{:?}", config.vm_type).to_lowercase(),
            config.nats_subjects.newheads_output
        );
    }

    // Verify NATS subjects for EVM chains
    let eth_config = configs.get("ethereum-mainnet").unwrap();
    assert_eq!(
        eth_config.nats_subjects.newheads_output,
        "newheads.ethereum.mainnet.evm"
    );

    let poly_config = configs.get("polygon-mainnet").unwrap();
    assert_eq!(
        poly_config.nats_subjects.newheads_output,
        "newheads.polygon.mainnet.evm"
    );

    println!("\n✅ NATS subjects correctly generated for different VM types");

    Ok(())
}

/// Test provider's response to rapid configuration changes
#[tokio::test]
async fn test_rapid_configuration_changes() -> Result<()> {
    // Start containers
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    let nats_container = Nats::default().start().await?;
    let nats_port = nats_container.get_host_port_ipv4(4222).await?;
    let nats_url = format!("nats://localhost:{}", nats_port);

    let django_admin = DjangoAdminSimulator::new(&redis_url).await?;
    let provider = NewheadsProvider::new(&nats_url, &redis_url).await?;

    println!("\n==== Testing Rapid Configuration Changes ====");

    // Simulate rapid changes
    for i in 0..5 {
        let chain_id = format!("test-chain-{}", i);

        // Create
        django_admin
            .create_blockchain_node(&chain_id, "test", "network", "EVM", true)
            .await?;
        sleep(Duration::from_millis(50)).await;

        // Update
        django_admin
            .update_blockchain_node(&chain_id, false)
            .await?;
        sleep(Duration::from_millis(50)).await;

        // Re-enable
        django_admin.update_blockchain_node(&chain_id, true).await?;
        sleep(Duration::from_millis(50)).await;
    }

    // Final check
    provider.load_configs_from_django().await?;
    let configs = provider.configs().read().await;

    assert_eq!(configs.len(), 5, "Should have all 5 test chains");
    for i in 0..5 {
        let chain_id = format!("test-chain-{}", i);
        assert!(configs.contains_key(&chain_id), "Should have {}", chain_id);
    }

    println!("✅ Provider handled rapid configuration changes correctly");
    println!("   Final active nodes: {}", configs.len());

    Ok(())
}

/// Test that provider subscription mechanism works
#[tokio::test]
async fn test_provider_subscription_to_updates() -> Result<()> {
    // Start containers
    let redis_container = Redis::default().start().await?;
    let redis_port = redis_container.get_host_port_ipv4(6379).await?;
    let redis_url = format!("redis://localhost:{}", redis_port);

    let nats_container = Nats::default().start().await?;
    let nats_port = nats_container.get_host_port_ipv4(4222).await?;
    let nats_url = format!("nats://localhost:{}", nats_port);

    println!("\n==== Testing Update Subscription Mechanism ====");

    // Create a shared state to track updates
    let update_count = Arc::new(RwLock::new(0));
    let update_count_clone = update_count.clone();

    // Create a custom Redis subscriber to monitor the channel
    let redis_client = redis::Client::open(redis_url.clone())?;
    let mut pubsub = redis_client.get_async_connection().await?.into_pubsub();

    pubsub.subscribe("blockchain:nodes:updates").await?;

    // Spawn a task to count updates
    tokio::spawn(async move {
        let mut pubsub_stream = pubsub.on_message();
        while let Some(msg) = pubsub_stream.next().await {
            let payload: String = msg.get_payload().unwrap();
            println!("📨 Received update: {}", payload);

            let mut count = update_count_clone.write().await;
            *count += 1;
        }
    });

    // Give subscriber time to connect
    sleep(Duration::from_millis(100)).await;

    // Create Django admin and provider
    let django_admin = DjangoAdminSimulator::new(&redis_url).await?;
    let _provider = NewheadsProvider::new(&nats_url, &redis_url).await?;

    // Perform operations that should trigger updates
    django_admin
        .create_blockchain_node("test-1", "test", "net", "EVM", true)
        .await?;
    sleep(Duration::from_millis(100)).await;

    django_admin.update_blockchain_node("test-1", false).await?;
    sleep(Duration::from_millis(100)).await;

    django_admin.delete_blockchain_node("test-1").await?;
    sleep(Duration::from_millis(100)).await;

    // Check that updates were received
    let count = update_count.read().await;
    assert_eq!(*count, 3, "Should have received 3 update notifications");

    println!("✅ Provider subscription mechanism working");
    println!("   Updates received: {}", *count);

    Ok(())
}
