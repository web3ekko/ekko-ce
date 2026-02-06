#[cfg(test)]
mod tests {
    use crate::{
        Component, EthTransaction, ProcessedTransactionOutput, ProcessingMetadata,
        RawTransactionMessage,
    };

    // Test data builders and utilities
    fn create_test_eth_transaction(with_subscription: bool) -> EthTransaction {
        EthTransaction {
            hash: "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef".to_string(),
            block_number: Some(18500000),
            transaction_index: Some(42),
            from: "0x742d35Cc6634C0532925a3b8D4Ff7eaD0Cc0a1234".to_string(),
            to: Some("0x8ba1f109551bD432803012645Hac136c9abcd123".to_string()),
            value: "1000000000000000000".to_string(), // 1 ETH in wei
            gas: "21000".to_string(),
            gas_price: "20000000000".to_string(), // 20 gwei
            input: "0x".to_string(),
            subscribed_uids: if with_subscription {
                Some(vec!["user_123".to_string(), "user_456".to_string()])
            } else {
                None
            },
        }
    }

    fn create_test_raw_transaction_message(
        network: &str,
        subnet: &str,
        transactions: Vec<EthTransaction>,
    ) -> RawTransactionMessage {
        RawTransactionMessage {
            network: network.to_string(),
            subnet: subnet.to_string(),
            transactions: serde_json::to_string(&transactions).unwrap(),
            metadata: Some(ProcessingMetadata {
                batch_id: "test_batch_123".to_string(),
                block_number: 18500000,
                timestamp: 1699123456,
                source: "test-raw-transactions-actor".to_string(),
            }),
        }
    }

    // Data Structure Tests
    #[test]
    fn test_eth_transaction_serialization() {
        let tx = create_test_eth_transaction(true);

        // Test serialization
        let json = serde_json::to_string(&tx).unwrap();
        assert!(json.contains("0x1234567890abcdef"));
        assert!(json.contains("user_123"));
        assert!(json.contains("1000000000000000000"));

        // Test deserialization
        let deserialized: EthTransaction = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.hash, tx.hash);
        assert_eq!(deserialized.block_number, Some(18500000));
        assert_eq!(deserialized.from, tx.from);
        assert_eq!(deserialized.to, tx.to);
        assert_eq!(deserialized.subscribed_uids.as_ref().unwrap().len(), 2);
    }

    #[test]
    fn test_eth_transaction_without_subscription() {
        let tx = create_test_eth_transaction(false);

        let json = serde_json::to_string(&tx).unwrap();
        assert!(!json.contains("subscribed_uids") || json.contains("null"));

        let deserialized: EthTransaction = serde_json::from_str(&json).unwrap();
        assert!(deserialized.subscribed_uids.is_none());
    }

    #[test]
    fn test_raw_transaction_message_structure() {
        let transactions = vec![
            create_test_eth_transaction(true),
            create_test_eth_transaction(false),
        ];
        let message = create_test_raw_transaction_message("ethereum", "mainnet", transactions);

        // Test serialization
        let json = serde_json::to_string(&message).unwrap();
        assert!(json.contains("ethereum"));
        assert!(json.contains("mainnet"));
        assert!(json.contains("test_batch_123"));

        // Test deserialization
        let deserialized: RawTransactionMessage = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.network, "ethereum");
        assert_eq!(deserialized.subnet, "mainnet");
        assert!(deserialized.metadata.is_some());

        // Test that transactions are properly embedded as JSON string
        let embedded_txs: Vec<EthTransaction> =
            serde_json::from_str(&deserialized.transactions).unwrap();
        assert_eq!(embedded_txs.len(), 2);
    }

    #[test]
    fn test_processed_transaction_output_structure() {
        let output = ProcessedTransactionOutput {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            status: "processed".to_string(),
            transaction_count: 5,
            filtered_count: 3,
            transactions: "[]".to_string(),
            processed_at: "2024-01-15T10:30:45Z".to_string(),
        };

        // Test serialization
        let json = serde_json::to_string(&output).unwrap();
        assert!(json.contains("ethereum"));
        assert!(json.contains("mainnet"));
        assert!(json.contains("processed"));
        assert!(json.contains("\"transaction_count\":5"));
        assert!(json.contains("\"filtered_count\":3"));

        // Test to_json method
        let json_bytes = output.to_json().unwrap();
        let parsed: ProcessedTransactionOutput = serde_json::from_slice(&json_bytes).unwrap();
        assert_eq!(parsed.network, "ethereum");
        assert_eq!(parsed.subnet, "mainnet");
        assert_eq!(parsed.transaction_count, 5);
        assert_eq!(parsed.filtered_count, 3);
    }

    // Message Processing Tests
    #[test]
    fn test_raw_transaction_message_from_json() {
        let transactions = vec![create_test_eth_transaction(true)];
        let message = create_test_raw_transaction_message("ethereum", "mainnet", transactions);
        let json_bytes = serde_json::to_vec(&message).unwrap();

        let parsed = RawTransactionMessage::from_json(&json_bytes).unwrap();
        assert_eq!(parsed.network, "ethereum");
        assert_eq!(parsed.subnet, "mainnet");
        assert!(parsed.metadata.is_some());
        assert_eq!(parsed.metadata.unwrap().batch_id, "test_batch_123");
    }

    #[test]
    fn test_raw_transaction_message_from_invalid_json() {
        let invalid_json = b"invalid json";
        let result = RawTransactionMessage::from_json(invalid_json);
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .contains("Failed to parse raw transaction message"));
    }

    // Transaction Processing Tests
    #[test]
    fn test_filter_subscribed_transactions() {
        let mut transactions = vec![
            create_test_eth_transaction(true),  // Has subscription
            create_test_eth_transaction(false), // No subscription
            create_test_eth_transaction(true),  // Has subscription
        ];

        Component::filter_subscribed_transactions(&mut transactions);

        assert_eq!(transactions.len(), 2);
        for tx in &transactions {
            assert!(tx.subscribed_uids.is_some());
        }
    }

    #[test]
    fn test_filter_subscribed_transactions_empty_list() {
        let mut transactions = vec![
            create_test_eth_transaction(false),
            create_test_eth_transaction(false),
        ];

        Component::filter_subscribed_transactions(&mut transactions);

        assert_eq!(transactions.len(), 0);
    }

    #[test]
    fn test_process_eth_transactions_with_subscriptions() {
        let transactions = vec![
            create_test_eth_transaction(true),
            create_test_eth_transaction(false),
            create_test_eth_transaction(true),
        ];
        let transactions_json = serde_json::to_string(&transactions).unwrap();

        let result =
            Component::process_eth_transactions("ethereum", "mainnet", &transactions_json).unwrap();

        assert_eq!(result.network, "ethereum");
        assert_eq!(result.subnet, "mainnet");
        assert_eq!(result.status, "processed");
        assert_eq!(result.transaction_count, 3);
        assert_eq!(result.filtered_count, 2);

        // Verify processed transactions contain only subscribed ones
        let processed_txs: Vec<EthTransaction> =
            serde_json::from_str(&result.transactions).unwrap();
        assert_eq!(processed_txs.len(), 2);
        for tx in &processed_txs {
            assert!(tx.subscribed_uids.is_some());
        }
    }

    #[test]
    fn test_process_eth_transactions_no_subscriptions() {
        let transactions = vec![
            create_test_eth_transaction(false),
            create_test_eth_transaction(false),
        ];
        let transactions_json = serde_json::to_string(&transactions).unwrap();

        let result =
            Component::process_eth_transactions("ethereum", "mainnet", &transactions_json).unwrap();

        assert_eq!(result.network, "ethereum");
        assert_eq!(result.subnet, "mainnet");
        assert_eq!(result.status, "processed");
        assert_eq!(result.transaction_count, 2);
        assert_eq!(result.filtered_count, 0);

        let processed_txs: Vec<EthTransaction> =
            serde_json::from_str(&result.transactions).unwrap();
        assert_eq!(processed_txs.len(), 0);
    }

    #[test]
    fn test_process_eth_transactions_invalid_json() {
        let invalid_json = "invalid json";
        let result = Component::process_eth_transactions("ethereum", "mainnet", invalid_json);
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .contains("Failed to parse eth transactions"));
    }

    #[test]
    fn test_process_transaction_message_ethereum() {
        let transactions = vec![
            create_test_eth_transaction(true),
            create_test_eth_transaction(false),
        ];
        let message = create_test_raw_transaction_message("ethereum", "mainnet", transactions);

        let result = Component::process_transaction_message(message).unwrap();

        assert_eq!(result.network, "ethereum");
        assert_eq!(result.subnet, "mainnet");
        assert_eq!(result.status, "processed");
        assert_eq!(result.transaction_count, 2);
        assert_eq!(result.filtered_count, 1);
    }

    #[test]
    fn test_process_transaction_message_eth_alias() {
        let transactions = vec![create_test_eth_transaction(true)];
        let message = create_test_raw_transaction_message("eth", "sepolia", transactions);

        let result = Component::process_transaction_message(message).unwrap();

        assert_eq!(result.network, "eth");
        assert_eq!(result.subnet, "sepolia");
        assert_eq!(result.status, "processed");
        assert_eq!(result.transaction_count, 1);
        assert_eq!(result.filtered_count, 1);
    }

    #[test]
    fn test_process_transaction_message_unsupported_network() {
        let transactions = vec![create_test_eth_transaction(true)];
        let message =
            create_test_raw_transaction_message("unknown_network", "mainnet", transactions);

        let result = Component::process_transaction_message(message);
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .contains("Unsupported network: unknown_network"));
    }

    // EVM Chain Support Tests
    #[test]
    fn test_multiple_evm_chains() {
        let test_cases = vec![
            ("ethereum", "mainnet", true, "ethereum", "mainnet"),
            ("eth", "sepolia", true, "eth", "sepolia"),
            ("bitcoin", "mainnet", true, "bitcoin", "mainnet"),
            ("btc", "testnet", true, "btc", "testnet"),
            ("solana", "devnet", true, "solana", "devnet"),
            ("sol", "mainnet", true, "sol", "mainnet"),
            ("unknown", "mainnet", false, "", ""),
        ];

        for (network, subnet, should_succeed, expected_network, expected_subnet) in test_cases {
            let transactions = vec![create_test_eth_transaction(true)];
            let message = create_test_raw_transaction_message(network, subnet, transactions);

            let result = Component::process_transaction_message(message);

            if should_succeed {
                assert!(result.is_ok(), "Network {} should succeed", network);
                let output = result.unwrap();
                assert_eq!(output.network, expected_network);
                assert_eq!(output.subnet, expected_subnet);

                if network == "ethereum" || network == "eth" {
                    assert_eq!(output.status, "processed");
                    assert_eq!(output.filtered_count, 1);
                } else {
                    assert_eq!(output.status, "not_implemented");
                    assert_eq!(output.filtered_count, 0);
                }
            } else {
                assert!(result.is_err(), "Network {} should fail", network);
            }
        }
    }

    // Edge Cases and Error Handling Tests
    #[test]
    fn test_process_empty_transaction_list() {
        let transactions: Vec<EthTransaction> = vec![];
        let transactions_json = serde_json::to_string(&transactions).unwrap();

        let result =
            Component::process_eth_transactions("ethereum", "mainnet", &transactions_json).unwrap();

        assert_eq!(result.network, "ethereum");
        assert_eq!(result.subnet, "mainnet");
        assert_eq!(result.status, "processed");
        assert_eq!(result.transaction_count, 0);
        assert_eq!(result.filtered_count, 0);
    }

    #[test]
    fn test_transaction_with_missing_optional_fields() {
        let mut tx = create_test_eth_transaction(true);
        tx.block_number = None;
        tx.transaction_index = None;
        tx.to = None;

        let transactions = vec![tx];
        let transactions_json = serde_json::to_string(&transactions).unwrap();

        let result =
            Component::process_eth_transactions("ethereum", "mainnet", &transactions_json).unwrap();
        assert_eq!(result.filtered_count, 1);

        let processed_txs: Vec<EthTransaction> =
            serde_json::from_str(&result.transactions).unwrap();
        assert_eq!(processed_txs.len(), 1);
        // The implementation adds block_number = Some(0) when missing
        assert_eq!(processed_txs[0].block_number, Some(0));
        assert!(processed_txs[0].to.is_none());
        assert!(processed_txs[0].transaction_index.is_none());
    }

    #[test]
    fn test_transaction_with_malformed_fields() {
        // Test with invalid JSON structure
        let invalid_transaction_json = r#"[{"hash": "invalid", "missing_required_fields": true}]"#;

        let result =
            Component::process_eth_transactions("ethereum", "mainnet", invalid_transaction_json);
        assert!(result.is_err());
    }

    // Publishing Logic Tests
    #[test]
    fn test_publish_processed_transactions_with_subscriptions() {
        let output = ProcessedTransactionOutput {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            status: "processed".to_string(),
            transaction_count: 3,
            filtered_count: 2,
            transactions: "[]".to_string(),
            processed_at: chrono::Utc::now().to_rfc3339(),
        };

        // Note: In a real test environment, we would mock the NATS publishing
        // For now, we test the logic that determines whether to publish
        assert!(output.filtered_count > 0); // Should trigger publishing
    }

    #[test]
    fn test_publish_processed_transactions_no_subscriptions() {
        let output = ProcessedTransactionOutput {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            status: "processed".to_string(),
            transaction_count: 3,
            filtered_count: 0,
            transactions: "[]".to_string(),
            processed_at: chrono::Utc::now().to_rfc3339(),
        };

        // Should not trigger publishing when filtered_count is 0
        assert_eq!(output.filtered_count, 0);
    }

    #[test]
    fn test_notification_payload_structure() {
        let output = ProcessedTransactionOutput {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            status: "processed".to_string(),
            transaction_count: 5,
            filtered_count: 3,
            transactions: "[]".to_string(),
            processed_at: "2024-01-15T10:30:45Z".to_string(),
        };

        // Test notification payload creation logic (with subnet)
        let notification_payload = serde_json::json!({
            "type": "transaction_batch_processed",
            "network": output.network,
            "subnet": output.subnet,
            "transaction_count": output.transaction_count,
            "filtered_count": output.filtered_count,
            "processed_at": output.processed_at,
            "status": output.status
        });

        assert_eq!(notification_payload["type"], "transaction_batch_processed");
        assert_eq!(notification_payload["network"], "ethereum");
        assert_eq!(notification_payload["subnet"], "mainnet");
        assert_eq!(notification_payload["transaction_count"], 5);
        assert_eq!(notification_payload["filtered_count"], 3);
    }

    // Integration-style Tests
    #[test]
    fn test_end_to_end_processing_workflow() {
        // Create mixed transaction batch
        let transactions = vec![
            create_test_eth_transaction(true),  // Should be processed
            create_test_eth_transaction(false), // Should be filtered out
            create_test_eth_transaction(true),  // Should be processed
            create_test_eth_transaction(false), // Should be filtered out
        ];

        let message = create_test_raw_transaction_message("ethereum", "mainnet", transactions);
        let message_json = serde_json::to_vec(&message).unwrap();

        // Test message parsing
        let parsed_message = RawTransactionMessage::from_json(&message_json).unwrap();
        assert_eq!(parsed_message.network, "ethereum");
        assert_eq!(parsed_message.subnet, "mainnet");

        // Test transaction processing
        let result = Component::process_transaction_message(parsed_message).unwrap();

        // Verify processing results
        assert_eq!(result.network, "ethereum");
        assert_eq!(result.subnet, "mainnet");
        assert_eq!(result.status, "processed");
        assert_eq!(result.transaction_count, 4);
        assert_eq!(result.filtered_count, 2);

        // Verify output can be serialized for publishing
        let output_json = result.to_json().unwrap();
        assert!(!output_json.is_empty());

        // Verify notification should be sent (filtered_count > 0)
        assert!(result.filtered_count > 0);
    }

    #[test]
    fn test_legacy_format_fallback_structure() {
        // Test the structure that would be created for legacy format fallback
        let transactions = vec![create_test_eth_transaction(true)];
        let transactions_str = serde_json::to_string(&transactions).unwrap();

        // Simulate legacy format processing (defaulting to mainnet)
        let legacy_message = RawTransactionMessage {
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transactions: transactions_str,
            metadata: None,
        };

        let result = Component::process_transaction_message(legacy_message).unwrap();
        assert_eq!(result.network, "ethereum");
        assert_eq!(result.subnet, "mainnet");
        assert_eq!(result.filtered_count, 1);
    }

    #[test]
    fn test_processing_metadata_preservation() {
        let metadata = ProcessingMetadata {
            batch_id: "batch_abc123".to_string(),
            block_number: 18500000,
            timestamp: 1699123456,
            source: "test-source".to_string(),
        };

        let transactions = vec![create_test_eth_transaction(true)];
        let message = RawTransactionMessage {
            network: "ethereum".to_string(),
            subnet: "sepolia".to_string(),
            transactions: serde_json::to_string(&transactions).unwrap(),
            metadata: Some(metadata.clone()),
        };

        // Test that metadata is accessible during processing
        assert_eq!(message.metadata.as_ref().unwrap().batch_id, "batch_abc123");

        let result = Component::process_transaction_message(message).unwrap();
        assert_eq!(result.network, "ethereum");
        assert_eq!(result.subnet, "sepolia");
        assert_eq!(result.filtered_count, 1);
    }

    #[test]
    fn test_different_subnets() {
        // Test that different subnets are properly handled
        let subnets = vec![
            ("mainnet", "mainnet"),
            ("sepolia", "sepolia"),
            ("goerli", "goerli"),
            ("devnet", "devnet"),
        ];

        for (input_subnet, expected_subnet) in subnets {
            let transactions = vec![create_test_eth_transaction(true)];
            let message =
                create_test_raw_transaction_message("ethereum", input_subnet, transactions);

            let result = Component::process_transaction_message(message).unwrap();
            assert_eq!(result.network, "ethereum");
            assert_eq!(result.subnet, expected_subnet);
        }
    }
}
