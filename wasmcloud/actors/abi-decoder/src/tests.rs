//! Unit tests for ABI decoder actor

#[cfg(test)]
mod unit_tests {
    use crate::decoder::AbiDecoder;
    use crate::types::*;

    /// Mock Redis getter for testing
    fn mock_redis_getter(key: &str) -> Option<String> {
        match key {
            "abi:ethereum:0xCachedContract" => Some(r#"[{
                "type": "function",
                "name": "approve",
                "inputs": [
                    {"name": "spender", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "nonpayable"
            }]"#.to_string()),
            _ => None,
        }
    }

    #[tokio::test]
    async fn test_batch_decoding() {
        let config = ActorConfig::default();
        let decoder = AbiDecoder::new(config).unwrap();
        
        let batch = BatchDecodeRequest {
            requests: vec![
                DecodeRequest {
                    to_address: "0x123".to_string(),
                    input_data: "0x".to_string(),
                    network: "ethereum".to_string(),
                    subnet: "mainnet".to_string(),
                    transaction_hash: "0x1".to_string(),
                    request_id: "req-1".to_string(),
                },
                DecodeRequest {
                    to_address: "".to_string(),
                    input_data: "0x608060405234801561001057600080fd5b50".to_string(),
                    network: "ethereum".to_string(),
                    subnet: "mainnet".to_string(),
                    transaction_hash: "0x2".to_string(),
                    request_id: "req-2".to_string(),
                },
                DecodeRequest {
                    to_address: "0x456".to_string(),
                    input_data: "0xa9059cbb0000000000000000000000000000".to_string(),
                    network: "ethereum".to_string(),
                    subnet: "mainnet".to_string(),
                    transaction_hash: "0x3".to_string(),
                    request_id: "req-3".to_string(),
                },
            ],
            batch_id: "batch-1".to_string(),
        };
        
        let result = decoder.decode_batch(batch, |_| None).await.unwrap();
        
        assert_eq!(result.results.len(), 3);
        assert_eq!(result.batch_id, "batch-1");
        assert_eq!(result.results[0].status, DecodingStatus::NativeTransfer);
        assert_eq!(result.results[1].status, DecodingStatus::ContractCreation);
        assert_eq!(result.results[2].status, DecodingStatus::AbiNotFound);
    }

    #[tokio::test]
    async fn test_redis_cache_fallback() {
        let config = ActorConfig::default();
        let decoder = AbiDecoder::new(config).unwrap();
        
        let request = DecodeRequest {
            to_address: "0xCachedContract".to_string(),
            input_data: "0x095ea7b3000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b60000000000000000000000000000000000000000000000000de0b6b3a7640000".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0xabc".to_string(),
            request_id: "req-redis".to_string(),
        };
        
        let result = decoder.decode_transaction(request, mock_redis_getter).await.unwrap();
        assert_eq!(result.status, DecodingStatus::Success);
        
        let decoded = result.decoded_function.unwrap();
        assert_eq!(decoded.name, "approve");
        assert_eq!(decoded.parameters.len(), 2);
        assert_eq!(result.abi_source, Some("redis".to_string()));
    }

    #[tokio::test]
    async fn test_cache_stats_tracking() {
        let config = ActorConfig::default();
        let decoder = AbiDecoder::new(config).unwrap();
        
        // Initial stats
        let stats = decoder.get_cache_stats().await;
        assert_eq!(stats.total_decodings, 0);
        
        // Perform some decodings
        for i in 0..5 {
            let request = DecodeRequest {
                to_address: "0x123".to_string(),
                input_data: "0x".to_string(),
                network: "ethereum".to_string(),
                subnet: "mainnet".to_string(),
                transaction_hash: format!("0x{}", i),
                request_id: format!("req-{}", i),
            };
            
            let _ = decoder.decode_transaction(request, |_| None).await;
        }
        
        let stats = decoder.get_cache_stats().await;
        assert_eq!(stats.total_decodings, 5);
        assert_eq!(stats.successful_decodings, 0); // All were native transfers, not "successful" decodings
    }

    #[tokio::test]
    async fn test_invalid_selector() {
        let config = ActorConfig::default();
        let decoder = AbiDecoder::new(config).unwrap();
        
        let request = DecodeRequest {
            to_address: "0x123".to_string(),
            input_data: "0xa9".to_string(), // Too short for selector
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0xshort".to_string(),
            request_id: "req-short".to_string(),
        };
        
        let result = decoder.decode_transaction(request, |_| None).await.unwrap();
        assert_eq!(result.status, DecodingStatus::DecodingFailed);
        assert!(result.error_message.unwrap().contains("Invalid input data"));
    }

    #[tokio::test]
    async fn test_complex_abi_decoding() {
        let config = ActorConfig::default();
        let decoder = AbiDecoder::new(config).unwrap();
        
        // Cache a complex ABI
        let cache_request = CacheAbiRequest {
            network: "ethereum".to_string(),
            contract_address: "0xComplexContract".to_string(),
            abi_json: r#"[{
                "type": "function",
                "name": "swapExactTokensForTokens",
                "inputs": [
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "amountOutMin", "type": "uint256"},
                    {"name": "path", "type": "address[]"},
                    {"name": "to", "type": "address"},
                    {"name": "deadline", "type": "uint256"}
                ],
                "outputs": [{"name": "amounts", "type": "uint256[]"}],
                "stateMutability": "nonpayable"
            }]"#.to_string(),
            source: "test".to_string(),
            verified: true,
        };
        
        decoder.cache_abi(cache_request).await.unwrap();
        
        // Try to decode a swap transaction
        let request = DecodeRequest {
            to_address: "0xComplexContract".to_string(),
            input_data: "0x38ed173900000000000000000000000000000000000000000000000000000000000186a0000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000a0000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4d8b600000000000000000000000000000000000000000000000000000000616615ec0000000000000000000000000000000000000000000000000000000000000002000000000000000000000000c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2000000000000000000000000dac17f958d2ee523a2206206994597c13d831ec7".to_string(),
            network: "ethereum".to_string(),
            subnet: "mainnet".to_string(),
            transaction_hash: "0xswap".to_string(),
            request_id: "req-swap".to_string(),
        };
        
        let result = decoder.decode_transaction(request, |_| None).await.unwrap();
        assert_eq!(result.status, DecodingStatus::Success);
        
        let decoded = result.decoded_function.unwrap();
        assert_eq!(decoded.name, "swapExactTokensForTokens");
        assert_eq!(decoded.parameters.len(), 5);
        assert_eq!(decoded.parameters[0].name, "amountIn");
        assert_eq!(decoded.parameters[1].name, "amountOutMin");
        assert_eq!(decoded.parameters[2].name, "path");
        assert_eq!(decoded.parameters[3].name, "to");
        assert_eq!(decoded.parameters[4].name, "deadline");
    }
}