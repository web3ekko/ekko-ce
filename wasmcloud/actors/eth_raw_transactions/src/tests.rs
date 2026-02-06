#[cfg(test)]
mod tests {
    use super::*;
    use crate::simplified_lib::*;
    use serde_json::json;

    #[test]
    fn test_network_config_redis_key() {
        // Test Redis key generation from packet info
        let key = NetworkConfig::redis_key("ethereum", "mainnet", "evm");
        assert_eq!(key, "nodes:ethereum:mainnet:evm");

        let key = NetworkConfig::redis_key("polygon", "mumbai", "evm");
        assert_eq!(key, "nodes:polygon:mumbai:evm");

        let key = NetworkConfig::redis_key("arbitrum", "mainnet", "evm");
        assert_eq!(key, "nodes:arbitrum:mainnet:evm");
    }

    #[test]
    fn test_network_config_serialization() {
        let config = NetworkConfig {
            rpc_urls: vec![
                "https://eth-mainnet.g.alchemy.com/v2/test".to_string(),
                "https://mainnet.infura.io/v3/test".to_string(),
            ],
            ws_urls: vec!["wss://eth-mainnet.g.alchemy.com/v2/test".to_string()],
            chain_id: Some(1),
            enabled: true,
        };

        // Test serialization
        let json = serde_json::to_string(&config).unwrap();
        assert!(json.contains("eth-mainnet.g.alchemy.com"));
        assert!(json.contains("\"enabled\":true"));

        // Test deserialization
        let deserialized: NetworkConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.rpc_urls.len(), 2);
        assert_eq!(deserialized.ws_urls.len(), 1);
        assert_eq!(deserialized.chain_id, Some(1));
        assert!(deserialized.enabled);
    }

    #[test]
    fn test_network_config_url_selection() {
        let config = NetworkConfig {
            rpc_urls: vec![
                "https://primary.example.com".to_string(),
                "https://backup.example.com".to_string(),
            ],
            ws_urls: vec!["wss://primary.example.com".to_string()],
            chain_id: Some(1),
            enabled: true,
        };

        // Test RPC URL selection
        let rpc_url = config.get_rpc_url().unwrap();
        assert_eq!(rpc_url, "https://primary.example.com");

        // Test WebSocket URL selection
        let ws_url = config.get_ws_url().unwrap();
        assert_eq!(ws_url, "wss://primary.example.com");
    }

    #[test]
    fn test_network_config_empty_urls() {
        let config = NetworkConfig {
            rpc_urls: vec![],
            ws_urls: vec![],
            chain_id: Some(1),
            enabled: true,
        };

        // Should return error for empty RPC URLs
        assert!(config.get_rpc_url().is_err());

        // Should return error for empty WebSocket URLs
        assert!(config.get_ws_url().is_err());
    }

    #[test]
    fn test_block_header_packet_info() {
        let block_header = BlockHeader {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            chain_id: "ethereum-mainnet".to_string(),
            chain_name: "Ethereum Mainnet".to_string(),
            block_number: 18500000,
            block_hash: "0x1234567890abcdef".to_string(),
            parent_hash: "0xabcdef1234567890".to_string(),
            timestamp: 1699000000,
            transaction_count: Some(150),
            received_at: "2024-01-15T10:30:45Z".to_string(),
            provider_id: "newheads-provider".to_string(),
        };

        // Test that we can extract network info from the packet
        assert_eq!(block_header.network, "ethereum");
        assert_eq!(block_header.subnet, "mainnet");
        assert_eq!(block_header.vm_type, "evm");

        // Test Redis key generation from packet
        let redis_key = NetworkConfig::redis_key(
            &block_header.network,
            &block_header.subnet,
            &block_header.vm_type,
        );
        assert_eq!(redis_key, "nodes:ethereum:mainnet:evm");
    }

    #[test]
    fn test_raw_transaction_structure() {
        let raw_tx = RawTransaction {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            transaction_hash: "0xabcdef1234567890".to_string(),
            block_number: 18500000,
            block_hash: "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
                .to_string(),
            block_timestamp: 1699000000,
            transaction_index: 0,
            from_address: "0x1234567890123456789012345678901234567890".to_string(),
            to_address: Some("0xabcdefabcdefabcdefabcdefabcdefabcdefabcdef".to_string()),
            value: "0xde0b6b3a7640000".to_string(),
            gas_limit: 21000,
            gas_price: "0x4a817c800".to_string(),
            input_data: "0x".to_string(),
            nonce: 42,
            chain_id: "0x1".to_string(),
            max_fee_per_gas: Some("0x6fc23ac00".to_string()),
            max_priority_fee_per_gas: Some("0x77359400".to_string()),
            transaction_type: Some(2),
            v: Some("0x1b".to_string()),
            r: Some(
                "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string(),
            ),
            s: Some(
                "0xfedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321".to_string(),
            ),
            processed_at: "2024-01-15T10:30:45Z".to_string(),
            processor_id: "eth-raw-transactions-actor".to_string(),
        };

        // Test serialization
        let json = serde_json::to_string(&raw_tx).unwrap();
        assert!(json.contains("ethereum"));
        assert!(json.contains("0xabcdef1234567890"));

        // Test that network info is preserved from block header
        assert_eq!(raw_tx.network, "ethereum");
        assert_eq!(raw_tx.subnet, "mainnet");
        assert_eq!(raw_tx.vm_type, "evm");
    }

    #[test]
    fn test_multiple_network_configs() {
        // Test configurations for different networks that would come from packets
        let networks = vec![
            ("ethereum", "mainnet", "evm"),
            ("polygon", "mainnet", "evm"),
            ("arbitrum", "mainnet", "evm"),
            ("ethereum", "goerli", "evm"),
            ("polygon", "mumbai", "evm"),
        ];

        for (network, subnet, vm_type) in networks {
            let redis_key = NetworkConfig::redis_key(network, subnet, vm_type);
            let expected_key = format!("nodes:{}:{}:{}", network, subnet, vm_type);
            assert_eq!(redis_key, expected_key);
        }
    }

    #[test]
    fn test_simplified_processor() {
        let processor = EthRawTransactionsProcessor::new();

        // Test block header
        let block_header = BlockHeader {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            chain_id: "ethereum-mainnet".to_string(),
            chain_name: "Ethereum Mainnet".to_string(),
            block_number: 18500000,
            block_hash: "0x1234567890abcdef".to_string(),
            parent_hash: "0xabcdef1234567890".to_string(),
            timestamp: 1699000000,
            transaction_count: Some(150),
            received_at: "2024-01-15T10:30:45Z".to_string(),
            provider_id: "newheads-provider".to_string(),
        };

        // Test config key generation
        let config_key = processor.get_config_key_for_block(&block_header);
        assert_eq!(config_key, "nodes:ethereum:mainnet:evm");
    }

    #[test]
    fn test_processor_with_config() {
        let processor = EthRawTransactionsProcessor::new();

        let block_header = BlockHeader {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            vm_type: "evm".to_string(),
            chain_id: "ethereum-mainnet".to_string(),
            chain_name: "Ethereum Mainnet".to_string(),
            block_number: 18500000,
            block_hash: "0x1234567890abcdef".to_string(),
            parent_hash: "0xabcdef1234567890".to_string(),
            timestamp: 1699000000,
            transaction_count: Some(150),
            received_at: "2024-01-15T10:30:45Z".to_string(),
            provider_id: "newheads-provider".to_string(),
        };

        let config = NetworkConfig {
            rpc_urls: vec![
                "https://eth-mainnet.g.alchemy.com/v2/test".to_string(),
                "https://mainnet.infura.io/v3/test".to_string(),
            ],
            ws_urls: vec!["wss://eth-mainnet.g.alchemy.com/v2/test".to_string()],
            chain_id: Some(1),
            enabled: true,
        };

        // Test processing with enabled config
        let result = processor.process_block_with_config(&block_header, &config);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), "https://eth-mainnet.g.alchemy.com/v2/test");

        // Test processing with disabled config
        let disabled_config = NetworkConfig {
            rpc_urls: vec!["https://test.com".to_string()],
            ws_urls: vec!["wss://test.com".to_string()],
            chain_id: Some(1),
            enabled: false,
        };

        let result = processor.process_block_with_config(&block_header, &disabled_config);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("disabled"));
    }

    #[test]
    fn test_example_configs() {
        let configs = EthRawTransactionsProcessor::create_example_configs();

        assert_eq!(configs.len(), 3);

        // Test Ethereum config
        let (network, subnet, vm_type, config) = &configs[0];
        assert_eq!(network, "ethereum");
        assert_eq!(subnet, "mainnet");
        assert_eq!(vm_type, "evm");
        assert!(config.enabled);
        assert_eq!(config.chain_id, Some(1));
        assert!(!config.rpc_urls.is_empty());
        assert!(!config.ws_urls.is_empty());

        // Test Polygon config
        let (network, subnet, vm_type, config) = &configs[1];
        assert_eq!(network, "polygon");
        assert_eq!(subnet, "mainnet");
        assert_eq!(vm_type, "evm");
        assert_eq!(config.chain_id, Some(137));

        // Test Arbitrum config
        let (network, subnet, vm_type, config) = &configs[2];
        assert_eq!(network, "arbitrum");
        assert_eq!(subnet, "mainnet");
        assert_eq!(vm_type, "evm");
        assert_eq!(config.chain_id, Some(42161));
    }
}
